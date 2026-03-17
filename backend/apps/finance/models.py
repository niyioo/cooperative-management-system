from django.db import models
from apps.core.models import TimeStampedUUIDModel
from django.conf import settings

class Income(TimeStampedUUIDModel):
    source = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date_received = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Income: {self.source} - {self.amount}"

class Expense(TimeStampedUUIDModel):
    category = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    date_incurred = models.DateField()
    description = models.TextField()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Expense: {self.category} - {self.amount}"