from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import SavingsAccount, SavingsTransaction


@admin.register(SavingsAccount)
class SavingsAccountAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('member', 'account_number', 'balance', 'last_updated')
    search_fields = ('account_number', 'member__first_name', 'member__last_name', 'member__membership_id')


@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Balances change only through apps.savings.services; transactions are a permanent record."""

    list_display = ('reference', 'account', 'transaction_type', 'amount', 'status', 'approved_by', 'created_at')
    list_filter = ('status', 'transaction_type', 'created_at')
    search_fields = ('reference', 'account__account_number', 'account__member__first_name')
