# Django + Vite + React デプロイ/静的ファイル配信トラブルシュート全記録

---

## 概要

このドキュメントは、Django + Vite + React プロジェクトの本番デプロイ時に発生した「React部分が表示されない」「/static/assets/xxx.jsが404」などの問題を、**どのような検証・設定変更・デバッグを経て解決したか**を時系列で詳細にまとめたものです。

---

## 1. 各ツールがテンプレートに対して行うこと

### 1.1 Vite
- `npm run build`で`frontend/dist/`配下にビルド成果物（JS/CSS/画像等）を出力
- `vite.config.ts`の`base`でURLのprefix（例: `/static/`）を決定
- `manifest.json`（例: `frontend/dist/manifest.json`）を出力
  - 各エントリの`file`や`css`は**baseを除いた相対パス**（例: `assets/main-xxxx.js`）

### 1.2 django-vite
- テンプレートで`{% vite_asset 'src/main.tsx' %}`等を使うと
  - manifest.jsonを参照し、該当エントリ（例: `'src/main.tsx'`）の`file`値（例: `assets/main-xxxx.js`）を取得
  - **Djangoの`STATIC_URL`（例: `/static/`）をprefixとして付与**し、`/static/assets/main-xxxx.js`のURLをテンプレートに埋め込む
- **manifest.jsonの内容は「staticなしの相対パス」が正しい**

### 1.3 Django
- テンプレート描画時に`{% vite_asset %}`で生成されたURLをHTMLに埋め込む
- `/static/`で始まるリクエストを受け取った時、urls.pyの設定に従いファイルを返す

---

## 2. npm run build から collectstatic までの流れと設定

### 2.1 主要な設定変数とフォルダ

- `vite.config.ts`
  - `base: '/static/'`
  - `build: { manifest: 'manifest.json', rollupOptions: { input: ... } }`
- `frontend/dist/` : Viteのビルド成果物出力先
- `frontend/dist/assets/` : JS/CSS/画像等
- `frontend/dist/manifest.json` : manifestファイル
- `config/settings.py`
  - `STATIC_URL = '/static/'`
  - `STATIC_ROOT = BASE_DIR / 'staticfiles'`
  - `STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'dist']`

### 2.2 ビルド・静的ファイル収集の流れ

1. `npm run build`  
   → `frontend/dist/assets/`と`frontend/dist/manifest.json`が生成される
2. `python manage.py collectstatic`  
   → `frontend/dist/`配下のファイルが`staticfiles/`配下にコピーされる
   - 例: `staticfiles/assets/main-xxxx.js`, `staticfiles/manifest.json`

---

## 3. manifest.jsonの必要性と役割

- **manifest.jsonは本番運用時に必須**
- django-viteは本番（DEBUG=False）でmanifest.jsonを参照し、エントリポイントやアセットのビルド後ファイル名を解決する
- manifest.jsonがないと`{% vite_asset %}`でエラー（500）になる

---

## 4. URL解決の方法と担当

### 4.1 テンプレート描画時
- **django-vite**がmanifest.jsonを参照し、`STATIC_URL`をprefixしてURLを生成

### 4.2 リクエスト時
- **Django本体**（gunicorn経由）がurls.pyのstatic配信Viewで`STATIC_ROOT`配下からファイルを返す
- **django-viteはリクエスト時には一切関与しない**

---

## 5. /static/の配信の仕組み

- gunicornや本番WSGIサーバは、Djangoのurls.pyで
  ```python
  urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
  ```
  またはカスタムViewを追加しない限り、/static/配下のリクエストを処理しない
- 本番ではNginxやS3等で配信するのが推奨（Django側のstatic配信設定は不要）

---

## 6. 検証・設定変更の履歴と効果

### 6.1 manifest.jsonの出力先・内容の修正
- `vite.config.ts`で`manifest: 'manifest.json'`を明示
- `rollupOptions.input`でエントリポイント（main.tsx, mapEntry.tsx等）を明示
- → manifest.jsonに必要なエントリが含まれるようになった

### 6.2 collectstaticの挙動確認
- `STATICFILES_DIRS`を`frontend/dist`に設定
- → collectstaticでassets/やmanifest.jsonがstaticfiles/配下にコピーされるようになった

### 6.3 gunicornでの配信問題
- `urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)`を追加
- → それでも配信できず

### 6.4 カスタムViewによるデバッグ
- `debug_static_serve`関数をurls.pyに追加し、リクエストパス・ファイルパス・存在有無・パーミッションをloggingで出力
- → 全てのファイルが`exists=True`で配信され、React部分も表示されるようになった

---

## 7. なぜカスタムViewで解決したのか？

- デフォルトのstatic()ではうまく配信できなかったが、カスタムViewで
    - パス解決を明示
    - パラメータを明示
    - loggingでI/Oが発生
  したことで、Djangoの内部挙動が安定し、配信が成功したと考えられる

---

## 8. 本番運用（Nginx/S3等）でのstatic配信

- 本番ではNginxやS3等で`/static/`配下のファイルを直接配信するのが推奨
- その場合、Djangoのurls.pyでのstatic配信設定は不要
- Nginx例:
    ```
    location /static/ {
        alias /path/to/staticfiles/;
    }
    ```

---

## 9. まとめ・教訓

- manifest.jsonの内容は「staticなしの相対パス」が正しい
- django-viteはテンプレート描画時のみ関与し、リクエスト時はDjangoのstatic配信Viewが処理
- gunicorn単体で配信する場合は、カスタムViewでパス解決・loggingを明示することで安定する場合がある
- 本番ではNginxやS3等で配信するのがベストプラクティス

---

## 10. 参考：主な設定ファイル例

### vite.config.ts
```js
export default defineConfig({
  base: '/static/',
  build: {
    manifest: 'manifest.json',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.tsx'),
        map: resolve(__dirname, 'src/mapEntry.tsx'),
      },
    },
  },
  // ...省略
})
```

### config/settings.py
```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'dist']
```

### config/urls.py（カスタムView例）
```python
from django.views.static import serve as original_serve
import os, logging
from django.urls import re_path

def debug_static_serve(request, path, document_root=None, show_indexes=False):
    abs_path = os.path.join(document_root, path)
    logging.error(f"[STATIC DEBUG] url={request.path} path={path} abs_path={abs_path}")
    logging.error(f"[STATIC DEBUG] exists={os.path.exists(abs_path)} perms={oct(os.stat(abs_path).st_mode) if os.path.exists(abs_path) else 'N/A'}")
    return original_serve(request, path, document_root=document_root, show_indexes=show_indexes)

urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', debug_static_serve, {'document_root': settings.STATIC_ROOT}),
]
```

---

## 11. 重要なポイントのまとめ

- **npm run build**: Viteがdist/assets/とmanifest.jsonを生成
- **collectstatic**: dist/配下のファイルをstaticfiles/にコピー
- **manifest.json**: 本番でdjango-viteがビルド成果物のファイル名解決に必須
- **テンプレート描画時**: django-viteがmanifest.jsonを参照し、STATIC_URLをprefixしてURLを生成
- **リクエスト時**: gunicorn→Django→urls.pyのstatic配信ViewがSTATIC_ROOT配下からファイルを返す
- **django-viteはリクエスト時には関与しない**
- **本番はNginx/S3等で配信するのが推奨**

---

**この記録がDjango＋Vite本番運用のトラブルシュート・再現防止に役立つことを願います。**

---

frontend/dist 以下のファイルの見本が欲しい。entryMapとかのエントリがどの様になっているかなどあると嬉しい。

#### staticfiles/assetsの内容
```
(venv) teshi@ip-10-0-138-113:~/dj-vt-map-test$ ls -al staticfiles/assets/
total 420
drwxrwxr-x 2 teshi teshi   4096 Jul 20 01:03 .
drwxrwxr-x 4 teshi teshi   4096 Jul 20 01:03 ..
-rw-r--r-- 1 teshi teshi 186661 Jul 20 01:03 client-aR2K8-ce.js
-rw-r--r-- 1 teshi teshi 188068 Jul 20 00:51 index-B8YDy9hk.js
-rw-r--r-- 1 teshi teshi   1385 Jul 20 00:51 index-D8b4DHJx.css
-rw-r--r-- 1 teshi teshi    904 Jul 20 01:03 main-3KBpVeYn.js
-rw-r--r-- 1 teshi teshi   1385 Jul 20 01:03 main-D8b4DHJx.css
-rw-r--r-- 1 teshi teshi  22321 Jul 20 01:03 map-Dr1BXjjW.js
-rw-r--r-- 1 teshi teshi   4126 Jul 20 01:03 react-CHdo91hT.svg
(venv) teshi@ip-10-0-138-113:~/dj-vt-map-test$ 
```
#### manifest.jsonの内容
```
(venv) teshi@ip-10-0-138-113:~/dj-vt-map-test$ cat staticfiles/manifest.json
{
  "_client-aR2K8-ce.js": {
    "file": "assets/client-aR2K8-ce.js",
    "name": "client"
  },
  "src/assets/react.svg": {
    "file": "assets/react-CHdo91hT.svg",
    "src": "src/assets/react.svg"
  },
  "src/main.tsx": {
    "file": "assets/main-3KBpVeYn.js",
    "name": "main",
    "src": "src/main.tsx",
    "isEntry": true,
    "imports": [
      "_client-aR2K8-ce.js"
    ],
    "css": [
      "assets/main-D8b4DHJx.css"
    ],
    "assets": [
      "assets/react-CHdo91hT.svg"
    ]
  },
  "src/mapEntry.tsx": {
    "file": "assets/map-Dr1BXjjW.js",
    "name": "map",
    "src": "src/mapEntry.tsx",
    "isEntry": true,
    "imports": [
      "_client-aR2K8-ce.js"
    ]
  }
}
(venv) teshi@ip-10-0-138-113:~/dj-vt-map-test$
```
