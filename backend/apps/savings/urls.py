from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SavingsAccountViewSet, SavingsTransactionViewSet

router = DefaultRouter()
router.register(r'accounts', SavingsAccountViewSet, basename='savings_account')
router.register(r'transactions', SavingsTransactionViewSet, basename='savings_transaction')

urlpatterns = [
    path('', include(router.urls)),
]