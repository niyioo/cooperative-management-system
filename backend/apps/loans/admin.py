from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, NoDeleteAdminMixin, ReadOnlyAdminMixin

from .models import (
    Loan,
    LoanApplication,
    LoanApplicationDocument,
    LoanGuarantor,
    LoanProduct,
    LoanRepayment,
    RepaymentAllocation,
    RepaymentInstallment,
)

# Workflow actions (approve, disburse, repay) live in the officer portal so they
# always go through the service layer, ledger and audit log. The Django admin
# is read-mostly for loans.


@admin.register(LoanProduct)
class LoanProductAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "interest_rate", "interest_rate_basis", "interest_method", "max_amount", "max_term_months", "is_active")
    list_filter = ("is_active", "interest_method", "interest_rate_basis")
    search_fields = ("name", "code")


class LoanApplicationDocumentInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = LoanApplicationDocument
    extra = 0
    fields = ("title", "file", "uploaded_by", "created_at")
    readonly_fields = fields


class LoanGuarantorInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = LoanGuarantor
    extra = 0
    fields = ("guarantor", "amount_guaranteed", "status", "responded_at")
    readonly_fields = fields


@admin.register(LoanApplication)
class LoanApplicationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "member", "product", "amount_requested", "term_months", "status", "submitted_at")
    list_filter = ("status", "product")
    search_fields = ("reference", "member__membership_number", "member__last_name")
    inlines = [LoanGuarantorInline, LoanApplicationDocumentInline]


class RepaymentInstallmentInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = RepaymentInstallment
    extra = 0
    fields = ("number", "due_date", "principal_due", "interest_due")
    readonly_fields = fields


@admin.register(Loan)
class LoanAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "member", "product", "principal", "term_months", "disbursed_on", "maturity_date", "status")
    list_filter = ("status", "product", "is_migrated")
    search_fields = ("reference", "member__membership_number", "member__last_name")
    inlines = [RepaymentInstallmentInline]


class RepaymentAllocationInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = RepaymentAllocation
    extra = 0
    fields = ("installment", "principal_amount", "interest_amount")
    readonly_fields = fields


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("transaction", "loan", "principal_component", "interest_component", "penalty_component", "created_at")
    search_fields = ("transaction__reference", "loan__reference")
    inlines = [RepaymentAllocationInline]
