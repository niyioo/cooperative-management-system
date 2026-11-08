from django.urls import path

from ..views.member import MyTransactionsView, StatementView

urlpatterns = [
    path("transactions/", MyTransactionsView.as_view(), name="transactions"),
    path("transactions/statement/", StatementView.as_view(), name="statement"),
]
