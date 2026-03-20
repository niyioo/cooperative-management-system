from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from simple_history.models import HistoricalRecords
import random, string

def generate_account_number():
    # Standard Nigerian NUBAN style (10 digits)
    return ''.join(random.choices(string.digits, k=10))

class SavingsAccount(TimeStampedUUIDModel):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='savings_account')
    account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        # ✅ Auto-generate account number on first save if it doesn't exist
        if not self.account_number:
            number = generate_account_number()
            # Ensure uniqueness
            while SavingsAccount.objects.filter(account_number=number).exists():
                number = generate_account_number()
            self.account_number = number
        super().save(*args, **kwargs)

    def __str__(self):
        # Safe fallback in case member name isn't set yet
        name = f"{self.member.first_name} {self.member.last_name}" if self.member.first_name else self.member.membership_id
        return f"Savings - {name} (₦{self.balance})"

class SavingsTransaction(TimeStampedUUIDModel):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        DIVIDEND = 'DIVIDEND', 'Dividend Payout'
        INTEREST = 'INTEREST', 'Interest Yield'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    account = models.ForeignKey(SavingsAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(blank=True, null=True)
    
    # Use 'accounts.CustomUser' string to avoid circular imports
    approved_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)
    history = HistoricalRecords() # ✅ Added history here too!

    def __str__(self):
        return f"{self.transaction_type} of ₦{self.amount} - {self.status}"