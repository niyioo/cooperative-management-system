from django.contrib import admin
from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment

@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'max_amount', 'max_duration_months', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    # ✅ Replaced 'principal' with 'principal_amount' and used 'application_date'
    list_display = ('loan_id', 'member', 'loan_product', 'principal_amount', 'status', 'application_date')
    list_filter = ('status', 'loan_product', 'application_date')
    search_fields = ('loan_id', 'member__membership_id', 'member__first_name', 'member__last_name')
    readonly_fields = ('loan_id', 'interest_amount', 'total_payable', 'balance_remaining')

@admin.register(LoanGuarantor)
class LoanGuarantorAdmin(admin.ModelAdmin):
    list_display = ('loan', 'guarantor_member', 'amount_guaranteed', 'status')
    list_filter = ('status',)
    search_fields = ('loan__loan_id', 'guarantor_member__membership_id')

@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_reference', 'loan', 'amount_paid', 'payment_date')
    search_fields = ('receipt_reference', 'loan__loan_id')
    readonly_fields = ('payment_date',)