from django.contrib import admin
from .models import Loan, LoanProduct

@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'max_amount', 'max_duration_months', 'is_active')
    list_editable = ('is_active',)

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'member_name', 'principal', 'status', 'balance_remaining', 'created_at')
    list_filter = ('status', 'loan_product')
    search_fields = ('loan_id', 'member__first_name', 'member__last_name', 'member__membership_id')
    
    # Custom actions to approve/reject right from the list
    actions = ['approve_loans', 'reject_loans']

    def member_name(self, obj):
        return f"{obj.member.first_name} {obj.member.last_name}"

    @admin.action(description='Approve selected loan applications')
    def approve_loans(self, request, queryset):
        queryset.update(status='APPROVED')
        self.message_user(request, "Selected loans have been approved.")

    @admin.action(description='Reject selected loan applications')
    def reject_loans(self, request, queryset):
        queryset.update(status='REJECTED')
        self.message_user(request, "Selected loans have been rejected.")