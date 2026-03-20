import uuid
from django.contrib import admin, messages
from django.utils import timezone
from django.db import transaction

from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment
# ✅ Import the Savings models so we can deposit the money
from apps.savings.models import SavingsAccount, SavingsTransaction 

@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'interest_rate', 'max_amount', 'max_duration_months', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('loan_id', 'member', 'loan_product', 'principal_amount', 'status', 'application_date')
    list_filter = ('status', 'loan_product', 'application_date')
    search_fields = ('loan_id', 'member__membership_id', 'member__first_name', 'member__last_name')
    readonly_fields = ('loan_id', 'interest_amount', 'total_payable', 'balance_remaining')
    
    # ✅ 1. Added 'disburse_loans' to the actions list
    actions = ['approve_loans', 'reject_loans', 'disburse_loans']

    @admin.action(description='✅ Approve selected loans')
    def approve_loans(self, request, queryset):
        updated_count = 0
        for loan in queryset:
            loan.status = 'APPROVED'
            loan.save()
            updated_count += 1
        self.message_user(request, f"Successfully approved {updated_count} loan(s).", level=messages.SUCCESS)

    @admin.action(description='❌ Reject selected loans')
    def reject_loans(self, request, queryset):
        updated_count = 0
        for loan in queryset:
            loan.status = 'REJECTED'
            loan.save()
            updated_count += 1
        self.message_user(request, f"Successfully rejected {updated_count} loan(s).", level=messages.SUCCESS)

    # ✅ 2. The new "Disburse Funds" Engine
    @admin.action(description='💸 Disburse selected APPROVED loans')
    def disburse_loans(self, request, queryset):
        disbursed_count = 0
        
        for loan in queryset:
            # Prevent accidental double-disbursements or disbursing pending loans
            if loan.status != 'APPROVED':
                self.message_user(request, f"Skipped {loan.loan_id}: Loan must be APPROVED before disbursement.", level=messages.WARNING)
                continue

            try:
                # transaction.atomic() ensures that if anything fails, no partial data is saved
                with transaction.atomic():
                    # 1. Update the Loan Status & Date
                    loan.status = 'ACTIVE'
                    loan.disbursed_at = timezone.now()
                    loan.save()

                    # 2. Find (or create) the member's Savings Account
                    savings_account, created = SavingsAccount.objects.get_or_create(member=loan.member)

                    # 3. Deposit the funds into the savings balance
                    savings_account.balance += loan.principal_amount
                    savings_account.save()

                    # 4. Generate an official transaction receipt in the Ledger
                    SavingsTransaction.objects.create(
                        account=savings_account,
                        transaction_type='DEPOSIT',
                        amount=loan.principal_amount,
                        reference=f"DISB-{uuid.uuid4().hex[:6].upper()}",
                        status='APPROVED',
                        description=f"Automated Loan Disbursement for {loan.loan_id}",
                        approved_by=request.user
                    )
                    
                    disbursed_count += 1
                    
            except Exception as e:
                self.message_user(request, f"System Error disbursing {loan.loan_id}: {str(e)}", level=messages.ERROR)

        if disbursed_count > 0:
            self.message_user(request, f"Successfully disbursed {disbursed_count} loan(s) and credited member savings accounts!", level=messages.SUCCESS)


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