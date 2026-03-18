from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LoanProductViewSet, LoanViewSet, LoanRepaymentViewSet

router = DefaultRouter()
router.register(r'products', LoanProductViewSet, basename='loan_product')
router.register(r'applications', LoanViewSet, basename='loan') # This creates /loans/applications/
router.register(r'repayments', LoanRepaymentViewSet, basename='loan_repayment')

urlpatterns = [
    path('', include(router.urls)),
]