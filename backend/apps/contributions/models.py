import uuid
from django.db import models
from apps.core.models import TimeStampedUUIDModel
from apps.members.models import Member
from django.conf import settings

class Contribution(TimeStampedUUIDModel):
    """
    Unified model tracking member assessments: Monthly Dues, Project Levies, and Penalty Fines.
    """
    class TypeChoices(models.TextChoices):
        MONTHLY_DUES = 'MONTHLY_DUES', 'Monthly Dues'
        LEVY = 'LEVY', 'Project Levy'
        FINE = 'FINE', 'Penalty Fine'

    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', 'Pending Payment'
        PAID = 'PAID', 'Paid'

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    type = models.CharField(max_length=20, choices=TypeChoices.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    
    reference_id = models.CharField(max_length=100, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    
    # Audit trail
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    date_paid = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            # e.g., FINE-A1B2C3D4 or DUES-A1B2C3D4
            prefix = self.type.split('_')[-1][:4] 
            self.reference_id = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member.first_name} - {self.get_type_display()} (₦{self.amount}) - {self.status}"