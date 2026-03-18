import uuid
from django.db import models
from django.conf import settings

class TimeStampedUUIDModel(models.Model):
    """
    An abstract base class model that provides self-updating
    ``created_at`` and ``updated_at`` fields, and uses UUID as PK.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

# --- NEW MODELS BELOW ---

class SystemSetting(TimeStampedUUIDModel):
    """
    Global settings for the Cooperative. 
    Usually, there should only ever be one instance of this model in the DB.
    """
    cooperative_name = models.CharField(max_length=255, default="BravEdge Solutions Cooperative")
    currency = models.CharField(max_length=10, default="NGN (₦)")
    registration_number = models.CharField(max_length=100, default="COOP-2026-001")

    def __str__(self):
        return f"Settings for {self.cooperative_name}"


class Notification(TimeStampedUUIDModel):
    """
    User-specific system alerts (e.g., Loan approved, payment overdue).
    """
    class TypeChoices(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'
        INFO = 'INFO', 'Information'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TypeChoices.choices, default=TypeChoices.INFO)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at'] # Newest notifications first

    def __str__(self):
        return f"{self.type} for {self.user.email}: {self.title}"