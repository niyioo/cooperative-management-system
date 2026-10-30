from django.contrib import admin, messages
from rest_framework.exceptions import APIException

from apps.core.admin import ReadOnlyAdminMixin

from . import services
from .models import Loan, LoanGuarantor, LoanProduct, LoanRepayment


@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'max_amount', 'max_duration_months', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


def _error_text(exc) -> str:
    detail = getattr(exc, 'detail', exc)
    if isinstance(detail, dict):
        return " ".join(str(v[0] if isinstance(v, list) else v) for v in detail.values())
    return str(detail)


@admin.register(Loan)
class LoanAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Loans change only through the same rules as the app (see apps.loans.services)."""

    list_display = ('loan_id', 'member', 'loan_product', 'principal_amount', 'balance_remaining', 'status', 'application_date')
    list_filter = ('status', 'loan_product', 'application_date')
    search_fields = ('loan_id', 'member__membership_id', 'member__first_name', 'member__last_name')
    actions = ['approve_loans', 'reject_loans', 'disburse_loans']

    def _run(self, request, queryset, step, label):
        done = 0
        for loan in queryset:
            try:
                step(loan, by=request.user)
                done += 1
            except APIException as exc:
                self.message_user(request, f"{loan.loan_id}: {_error_text(exc)}", level=messages.WARNING)
        if done:
            self.message_user(request, f"{label} {done} loan(s).", level=messages.SUCCESS)

    @admin.action(description='Approve selected pending loans')
    def approve_loans(self, request, queryset):
        self._run(request, queryset, services.approve, "Approved")

    @admin.action(description='Reject selected pending loans')
    def reject_loans(self, request, queryset):
        self._run(request, queryset, services.reject, "Rejected")

    @admin.action(description='Disburse selected approved loans')
    def disburse_loans(self, request, queryset):
        self._run(request, queryset, services.disburse, "Disbursed")


@admin.register(LoanGuarantor)
class LoanGuarantorAdmin(admin.ModelAdmin):
    list_display = ('loan', 'guarantor_member', 'amount_guaranteed', 'status')
    list_filter = ('status',)
    search_fields = ('loan__loan_id', 'guarantor_member__membership_id')


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('receipt_reference', 'loan', 'amount_paid', 'payment_date', 'received_by')
    search_fields = ('receipt_reference', 'loan__loan_id')
