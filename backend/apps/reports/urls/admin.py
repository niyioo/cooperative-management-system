from django.urls import path

from ..views.admin import DashboardView, ReportCatalogueView, ReportView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/", ReportCatalogueView.as_view(), name="report-catalogue"),
    path("reports/<slug:key>/", ReportView.as_view(), name="report"),
]
