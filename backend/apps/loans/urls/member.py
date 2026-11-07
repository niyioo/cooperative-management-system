from django.urls import path
from rest_framework.routers import SimpleRouter

from ..views.member import (
    GuarantorLookupView,
    MyGuaranteeRequestViewSet,
    MyLoanApplicationViewSet,
    MyLoanProductViewSet,
    MyLoanViewSet,
)

router = SimpleRouter()
router.register("loan-products", MyLoanProductViewSet, basename="my-loan-product")
router.register("loan-applications", MyLoanApplicationViewSet, basename="my-loan-application")
router.register("loans", MyLoanViewSet, basename="my-loan")
router.register("guarantee-requests", MyGuaranteeRequestViewSet, basename="my-guarantee-request")

urlpatterns = [
    path("guarantor-lookup/", GuarantorLookupView.as_view(), name="guarantor-lookup"),
    *router.urls,
]
