from django.contrib import admin
from .models import SavingsAccount, SavingsTransaction

@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ('member', 'account_number', 'balance', 'last_updated')
    search_fields = ('account_number', 'member__first_name', 'member__last_name', 'member__membership_id')
    readonly_fields = ('balance', 'account_number') # Protect the money and ID!

@admin.register(SavingsTransaction)
class SavingsTransactionAdmin(admin.ModelAdmin):
    # ✅ Matches your model exactly
    list_display = ('reference', 'account', 'transaction_type', 'amount', 'status', 'created_at')
    
    # ✅ Side-filters
    list_filter = ('status', 'transaction_type', 'created_at')
    
    search_fields = ('reference', 'account__account_number', 'account__member__first_name')
    readonly_fields = ('reference',)