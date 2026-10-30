import uuid
from decimal import ROUND_HALF_UP, Decimal
from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member

class LoanProduct(TimeStampedUUIDModel):
    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage (e.g., 5.00 for 5%)")
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_duration_months = models.IntegerField()
    description = models.TextField(blank=True, null=True) # Added for admin clarity
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.interest_rate}%)"

class Loan(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved (Awaiting Disbursement)'
        ACTIVE = 'ACTIVE', 'Active (Disbursed)'
        REJECTED = 'REJECTED', 'Rejected'
        COMPLETED = 'COMPLETED', 'Completed'
        DEFAULTED = 'DEFAULTED', 'Defaulted'

    loan_id = models.CharField(max_length=20, unique=True, blank=True)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loans')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.RESTRICT)
    
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    duration_months = models.IntegerField()
    purpose = models.TextField(blank=True, null=True) # ✅ ADDED: Matches React "Loan Purpose"
    
    # Calculated fields
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_remaining = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    application_date = models.DateField(auto_now_add=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Generate friendly ID
        if not self.loan_id:
            self.loan_id = f"LN-{uuid.uuid4().hex[:6].upper()}"
            
        # Calculate totals on initial creation. (The UUID primary key is set before
        # the first save, so `self.pk` can't tell a new loan from an old one.)
        if self._state.adding:
            # Flat rate on the principal: Principal × Rate / 100, rounded to the kobo.
            interest = (self.principal_amount * self.loan_product.interest_rate / Decimal('100')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            self.interest_amount = interest
            self.total_payable = self.principal_amount + interest
            self.balance_remaining = self.total_payable

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.loan_id} - {self.member.first_name} ({self.status})"

class LoanGuarantor(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Consent'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='guarantors')
    guarantor_member = models.ForeignKey(Member, on_delete=models.RESTRICT, related_name='guaranteed_loans')
    amount_guaranteed = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

class LoanRepayment(TimeStampedUUIDModel):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    receipt_reference = models.CharField(max_length=100, unique=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)