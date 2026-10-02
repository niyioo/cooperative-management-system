from django.urls import path
from rest_framework.routers import SimpleRouter

from ..views.admin import EligibilityView, LoanApplicationViewSet, LoanProductViewSet, LoanViewSet

router = SimpleRouter()
router.register("loans/products", LoanProductViewSet, basename="loan-product")
router.register("loans/applications", LoanApplicationViewSet, basename="loan-application")
router.register("loans", LoanViewSet, basename="loan")  # UUID lookups, so no clash with the prefixes above

urlpatterns = [
    path("loans/eligibility/", EligibilityView.as_view(), name="loan-eligibility"),
    *router.urls,
]
