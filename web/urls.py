from django.urls import path
from .views import index, map_view

urlpatterns = [
    path('', index, name='index'),
    path('map/', map_view, name='map'),
]
