from decimal import Decimal
from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from django.conf import settings

class LoanProduct(TimeStampedUUIDModel):
    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage (e.g., 5.00 for 5%)")
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_duration_months = models.IntegerField()
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

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='loans')
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.RESTRICT)
    principal_amount = models.DecimalField(max_digits=15, decimal_places=2)
    duration_months = models.IntegerField()
    
    # Calculated fields
    interest_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_payable = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_remaining = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    application_date = models.DateField(auto_now_add=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk: # Only calculate on creation
            # Simple flat interest calculation for cooperative: (P * R) / 100
            interest = (self.principal_amount * self.loan_product.interest_rate) / Decimal('100.00')
            self.interest_amount = interest
            self.total_payable = self.principal_amount + interest
            self.balance_remaining = self.total_payable
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Loan {self.id} - {self.member.first_name} - {self.status}"

class LoanGuarantor(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Consent'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='guarantors')
    guarantor_member = models.ForeignKey(Member, on_delete=models.RESTRICT, related_name='guaranteed_loans')
    amount_guaranteed = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"{self.guarantor_member} guaranteeing {self.loan}"

class LoanRepayment(TimeStampedUUIDModel):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    receipt_reference = models.CharField(max_length=100, unique=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Repayment {self.receipt_reference} for Loan {self.loan.id}"