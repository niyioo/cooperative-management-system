from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, NoDeleteAdminMixin, ReadOnlyAdminMixin

from .models import InvestmentAccount, InvestmentProduct, InvestmentReturn, InvestmentTransaction


@admin.register(InvestmentProduct)
class InvestmentProductAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "min_amount", "lock_in_months", "dividend_eligible", "is_active")
    list_filter = ("is_active", "dividend_eligible")
    search_fields = ("name", "code")


@admin.register(InvestmentAccount)
class InvestmentAccountAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("account_number", "member", "product", "opened_on", "status")
    list_filter = ("product", "status")
    search_fields = ("account_number", "member__membership_number", "member__last_name")
    autocomplete_fields = ("member",)
    readonly_fields = ("account_number",)


@admin.register(InvestmentReturn)
class InvestmentReturnAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("product", "financial_year", "amount_earned", "recorded_by", "created_at")
    list_filter = ("financial_year", "product")


@admin.register(InvestmentTransaction)
class InvestmentTransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "member", "investment_account", "txn_type", "entry_side", "amount", "status")
    list_filter = ("txn_type", "status")
    search_fields = ("reference", "member__membership_number", "investment_account__account_number")
