from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SystemSettingViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'settings', SystemSettingViewSet, basename='setting')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]