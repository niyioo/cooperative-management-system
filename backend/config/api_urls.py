"""
API v1 routing.

  /api/v1/auth/   authentication and password management
  /api/v1/me/     member self-service — every view is scoped to request.user.member
  /api/v1/admin/  officer portal — every view requires IsOfficer + a named permission

Each app contributes `urls/member.py` and `urls/admin.py` modules as its
endpoints are built (Phases 3–11).
"""
from django.urls import include, path

from apps.common.views import HealthCheckView

auth_patterns = [
    path("", include("apps.accounts.urls.auth")),
]
member_patterns = [
    path("", include(f"apps.{app}.urls.member"))
    for app in ("members", "savings", "loans", "investments", "dividends", "ledger", "closures", "notifications")
]
admin_patterns = [
    path("", include("apps.accounts.urls.admin")),
    path("", include("apps.configuration.urls.admin")),
    path("", include("apps.members.urls.admin")),
    path("", include("apps.savings.urls.admin")),
    path("", include("apps.loans.urls.admin")),
    path("", include("apps.investments.urls.admin")),
    path("", include("apps.dividends.urls.admin")),
    path("", include("apps.audit.urls.admin")),
    path("", include("apps.closures.urls.admin")),
    path("", include("apps.reports.urls.admin")),
    path("", include("apps.ledger.urls.admin")),
    path("", include("apps.notifications.urls.admin")),
]

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/", include((auth_patterns, "auth"))),
    path("me/", include((member_patterns, "me"))),
    # Namespace "officer" avoids clashing with the Django admin's "admin" namespace.
    path("admin/", include((admin_patterns, "officer"))),
]
