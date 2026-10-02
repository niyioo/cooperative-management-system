from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, NoDeleteAdminMixin

from .models import CooperativeSettings, Department


@admin.register(CooperativeSettings)
class CooperativeSettingsAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "name",
                    "short_name",
                    "parent_institution",
                    "registration_number",
                    "address",
                    "email",
                    "phone",
                    "logo",
                )
            },
        ),
        (
            "Formats and calendar",
            {
                "fields": (
                    "currency_code",
                    "membership_number_format",
                    "financial_year_start_month",
                    "dividend_processing_month",
                )
            },
        ),
        (
            "Rules",
            {
                "fields": (
                    "member_withdrawal_requests_enabled",
                    "closure_disables_portal_login",
                    "maker_checker_types",
                    "loan_overdue_grace_days",
                    "contributions_tracked_from",
                    "session_idle_timeout_minutes",
                )
            },
        ),
    )

    def has_add_permission(self, request):
        return not CooperativeSettings.objects.exists()


@admin.register(Department)
class DepartmentAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
