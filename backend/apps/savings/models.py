from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
import random, string

def generate_account_number():
    return ''.join(random.choices(string.digits, k=10))

class SavingsAccount(TimeStampedUUIDModel):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='savings_account')
    account_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Savings - {self.member.first_name} {self.member.last_name} ({self.balance})"

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
    approved_by = models.ForeignKey('accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} - {self.status}"