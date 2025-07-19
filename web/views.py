from django.shortcuts import render

def index(request):
    return render(request, 'index.html')

def map_view(request):
    # 本来は環境変数やsettingsからAPIキーを取得するのが安全ですが、ここでは仮値を使用
    context = {
        "api_key": "YOUR_GOOGLE_MAPS_API_KEY",
        "lat": 35.681236,   # 東京駅
        "lng": 139.767125,
        "zoom": 14,
    }
    return render(request, 'map.html', context)
