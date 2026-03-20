from django.contrib import admin
from .models import SavingsAccount, SavingsTransaction

@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ('account_number', 'member_name', 'balance', 'updated_at')
    search_fields = ('account_number', 'member__membership_id', 'member__first_name')
    readonly_fields = ('balance', 'account_number') # Keep balance read-only to prevent manual hacks

    def member_name(self, obj):
        return f"{obj.member.first_name} {obj.member.last_name}"

@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'account', 'type', 'amount', 'date')
    list_filter = ('type', 'date')
    search_fields = ('transaction_id', 'account__account_number')