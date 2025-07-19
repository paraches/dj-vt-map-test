"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include the URLs from the web app
    path('', include('web.urls')),
]

# 静的ファイル配信（gunicorn等WSGIサーバ用）＋デバッグログ
from django.conf import settings
from django.views.static import serve as original_serve
import os
import logging
from django.urls import re_path

def debug_static_serve(request, path, document_root=None, show_indexes=False):
    abs_path = os.path.join(document_root, path)
    logging.error(f"[STATIC DEBUG] url={request.path} path={path} abs_path={abs_path}")
    logging.error(f"[STATIC DEBUG] exists={os.path.exists(abs_path)} perms={oct(os.stat(abs_path).st_mode) if os.path.exists(abs_path) else 'N/A'}")
    return original_serve(request, path, document_root=document_root, show_indexes=show_indexes)

urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', debug_static_serve, {'document_root': settings.STATIC_ROOT}),
]
