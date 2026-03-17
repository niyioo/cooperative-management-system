from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from django.conf import settings

class ShareAccount(TimeStampedUUIDModel):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='share_account')
    total_shares = models.PositiveIntegerField(default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Shares - {self.member.membership_id} ({self.total_shares})"

class ShareTransaction(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    account = models.ForeignKey(ShareAccount, on_delete=models.CASCADE, related_name='transactions')
    shares_bought = models.PositiveIntegerField()
    price_per_share = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.total_amount = self.shares_bought * self.price_per_share
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Buy {self.shares_bought} shares for {self.account.member.membership_id}"