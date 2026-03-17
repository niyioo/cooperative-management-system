from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from django.conf import settings

class ContributionType(TimeStampedUUIDModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_mandatory = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {'Mandatory' if self.is_mandatory else 'Voluntary'}"

class ContributionRecord(TimeStampedUUIDModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    contribution_type = models.ForeignKey(ContributionType, on_delete=models.RESTRICT)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    receipt_reference = models.CharField(max_length=100, unique=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.member.first_name} - {self.contribution_type.name} ({self.amount_paid})"

class Fine(TimeStampedUUIDModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='fines')
    reason = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    date_issued = models.DateField(auto_now_add=True)
    date_paid = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Fine: {self.reason} - {self.member.membership_id} ({'Paid' if self.is_paid else 'Unpaid'})"