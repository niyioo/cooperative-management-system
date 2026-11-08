from django.contrib import admin

from apps.common.admin import ReadOnlyAdminMixin

from .models import AccountClosureRequest


@admin.register(AccountClosureRequest)
class AccountClosureRequestAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "member", "reason_category", "status", "created_at", "decided_by", "closed_at")
    list_filter = ("status", "reason_category")
    search_fields = ("reference", "member__membership_number", "member__last_name")
