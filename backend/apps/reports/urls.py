from django.urls import path
from .views import DashboardSummaryView, DashboardExportPDFView

urlpatterns = [
    path('dashboard-summary/', DashboardSummaryView.as_view(), name='dashboard_summary'),
    # ✅ Add this for the "Generate Report" button
    path('dashboard-summary/export_pdf/', DashboardExportPDFView.as_view(), name='dashboard_export_pdf'),
]