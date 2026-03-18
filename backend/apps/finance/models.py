import uuid
from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from django.conf import settings

class LedgerEntry(TimeStampedUUIDModel):
    """
    Global Cooperative Finance Ledger.
    Tracks all cooperative income and expenses in one unified table.
    """
    class EntryType(models.TextChoices):
        INCOME = 'INCOME', 'Income'
        EXPENSE = 'EXPENSE', 'Expense'

    type = models.CharField(max_length=10, choices=EntryType.choices)
    category = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date = models.DateField()
    description = models.TextField()
    reference_id = models.CharField(max_length=100, unique=True, blank=True)
    
    # ✅ THE FIX: Link the transaction to a specific member (Optional, because some expenses like "Office Rent" won't have a member)
    member = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name='ledger_transactions')
    
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            prefix = "INC" if self.type == self.EntryType.INCOME else "EXP"
            self.reference_id = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type}: {self.category} - ₦{self.amount}"