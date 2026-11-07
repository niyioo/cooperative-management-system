from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, NoDeleteAdminMixin, ReadOnlyAdminMixin

from .models import SavingsAccount, SavingsCycle, SavingsProduct, SavingsTransaction


@admin.register(SavingsProduct)
class SavingsProductAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "kind", "cycle_start_month", "cycle_end_month", "is_mandatory", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "code")


@admin.register(SavingsCycle)
class SavingsCycleAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("__str__", "year", "start_date", "end_date", "expected_monthly_contribution", "status")
    list_filter = ("status", "product", "year")
    readonly_fields = ("opened_by", "opened_at", "closed_by", "closed_at")


@admin.register(SavingsAccount)
class SavingsAccountAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("account_number", "member", "product", "cycle", "status", "opened_on")
    list_filter = ("product", "status", "cycle__year")
    search_fields = ("account_number", "member__membership_number", "member__last_name")
    autocomplete_fields = ("member",)
    readonly_fields = ("account_number",)


@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "member", "savings_account", "txn_type", "entry_side", "amount", "period", "status")
    list_filter = ("txn_type", "status")
    search_fields = ("reference", "member__membership_number", "savings_account__account_number")
