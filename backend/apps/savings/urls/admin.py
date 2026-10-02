from django.urls import path
from rest_framework.routers import SimpleRouter

from ..views.admin import (
    ContributionView,
    SavingsAccountViewSet,
    SavingsCycleViewSet,
    SavingsProductViewSet,
    WithdrawalView,
)

router = SimpleRouter()
router.register("savings/products", SavingsProductViewSet, basename="savings-product")
router.register("savings/cycles", SavingsCycleViewSet, basename="savings-cycle")
router.register("savings/accounts", SavingsAccountViewSet, basename="savings-account")

urlpatterns = [
    path("savings/contributions/", ContributionView.as_view(), name="savings-contribution"),
    path("savings/withdrawals/", WithdrawalView.as_view(), name="savings-withdrawal"),
    *router.urls,
]
