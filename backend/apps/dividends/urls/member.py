from django.urls import path

from ..views.member import MyDividendsView

urlpatterns = [path("dividends/", MyDividendsView.as_view(), name="dividends")]
