# AWS RDS PostgreSQL + PostGIS × Django + GeoDjango 本番運用手順・注意点

## 1. 概要・前提
- AWS RDSでPostgreSQL（PostGIS拡張有効）を本番DBとし、Django/GeoDjangoアプリを運用するための設定・運用ガイド
- 開発環境はsqlite+spatialite、本番はPostgreSQL+PostGISで切り替え
- 設定値はpython-decoupleで.env管理

---

## 2. RDS(PostgreSQL)の作成とPostGIS拡張

1. AWSコンソールでRDSインスタンス（PostgreSQL）を作成
2. DB作成後、**RDSのmasterユーザーでDBに接続し、PostGIS拡張を有効化**
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
   - 既に有効なら再実行不要
   - `\dx` で拡張一覧、`SELECT PostGIS_Version();` でバージョン確認

---

## 3. DBユーザーの使い分け

- **最初のmigrate時のみmasterユーザーでDjangoを設定**
- 以降は一般ユーザー（CREATE EXTENSION権限不要）で運用
- 一般ユーザーには「public」スキーマへのアクセス権限が必要

---

## 4. Django settings.pyのDATABASES設定例（decouple統一）

```python
from decouple import config

DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.spatialite',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    # SpatiaLiteパス設定（省略）
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': config('POSTGRES_DB', default='your_db_name'),
            'USER': config('POSTGRES_USER', default='your_db_user'),
            'PASSWORD': config('POSTGRES_PASSWORD', default='your_db_password'),
            'HOST': config('POSTGRES_HOST', default='your-db-instance.xxxxx.ap-northeast-1.rds.amazonaws.com'),
            'PORT': config('POSTGRES_PORT', default='5432'),
            # 'OPTIONS': {'options': '-c search_path=public'},  # 必要に応じて
        }
    }
```

### .envサンプル（本番用）
```
DJANGO_DEBUG=False
POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=your-db-instance.xxxxx.ap-northeast-1.rds.amazonaws.com
POSTGRES_PORT=5432
```

---

## 5. requirements-prod.txtサンプル

```
-r requirements.txt
psycopg[binary]
```

---

## 6. migrate時の権限運用フロー

1. **初回のみ** settings.pyのPOSTGRES_USER/PASSWORDをRDSのmasterユーザーにして
   ```
   python manage.py migrate
   ```
   - PostGIS拡張が無い場合は自動でCREATE EXTENSIONされる
2. migrate完了後、.envのPOSTGRES_USER/PASSWORDを一般ユーザーに戻す
3. 以降は一般ユーザーでmigrate可能

---

## 7. トラブルシュート

- `permission denied to create extension "postgis"`  
  → masterユーザーでmigrateする or 事前にCREATE EXTENSIONしておく
- `relation "spatial_ref_sys" does not exist`  
  → PostGIS拡張が有効か、スキーマ(public)が正しいか確認
- `psycopg2.errors.InsufficientPrivilege`  
  → DBユーザー権限を見直す
- migrate時にCREATE EXTENSIONしようとする  
  → 既に拡張が有効か、Djangoが参照できるか確認

---

## 8. 運用ベストプラクティス

- .envでDB接続情報を一元管理し、git管理しない
- requirements.txtとrequirements-prod.txtで依存を分離
- 本番DBのバックアップ・スナップショットを定期取得
- RDSのパラメータグループで「rds.force_ssl=1」等のセキュリティ設定を推奨
- DjangoのALLOWED_HOSTSやSECURE_SSL_REDIRECT等も本番用に設定

---

## 9. 参考

- [Django公式 GeoDjango/PostGIS](https://docs.djangoproject.com/ja/5.2/ref/contrib/gis/db-api/)
- [AWS公式 RDS PostgreSQL 拡張](https://docs.aws.amazon.com/ja_jp/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html#PostgreSQL.Concepts.General.FeatureSupport.Extensions)
