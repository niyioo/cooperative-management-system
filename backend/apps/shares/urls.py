from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShareAccountViewSet, ShareTransactionViewSet

router = DefaultRouter()
router.register(r'accounts', ShareAccountViewSet, basename='share_account')
router.register(r'transactions', ShareTransactionViewSet, basename='share_transaction')

urlpatterns = [
    path('', include(router.urls)),
]