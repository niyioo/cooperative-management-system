from django.urls import path

from ..views.member import (
    MyChristmasSavingsView,
    MyMonthlyContributionView,
    MySavingsTransactionsView,
    MySavingsView,
)

urlpatterns = [
    path("savings/", MySavingsView.as_view(), name="savings"),
    path("savings/monthly-contribution/", MyMonthlyContributionView.as_view(), name="savings-monthly-contribution"),
    path("savings/christmas/", MyChristmasSavingsView.as_view(), name="savings-christmas"),
    path("savings/accounts/<uuid:account_id>/transactions/", MySavingsTransactionsView.as_view(), name="savings-transactions"),
]
