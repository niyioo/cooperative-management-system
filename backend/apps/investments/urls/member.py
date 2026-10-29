from django.urls import path

from ..views.member import MyInvestmentsView, MyInvestmentTransactionsView

urlpatterns = [
    path("investments/", MyInvestmentsView.as_view(), name="investments"),
    path("investments/<uuid:account_id>/transactions/", MyInvestmentTransactionsView.as_view(), name="investment-transactions"),
]
