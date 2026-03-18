from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LedgerEntryViewSet

router = DefaultRouter()
# This matches exactly what the React frontend is expecting!
router.register(r'ledger', LedgerEntryViewSet, basename='ledger')

urlpatterns = [
    path('', include(router.urls)),
]