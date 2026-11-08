from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel


class Notification(TimeStampedModel):
    """A message for one user, e.g. 'Your loan application was approved'."""

    class Category(models.TextChoices):
        LOAN = "LOAN", "Loans"
        SAVINGS = "SAVINGS", "Savings"
        INVESTMENT = "INVESTMENT", "Investments"
        DIVIDEND = "DIVIDEND", "Dividends"
        CLOSURE = "CLOSURE", "Account closure"
        APPROVAL = "APPROVAL", "Pending approval"
        MESSAGE = "MESSAGE", "Message from the cooperative"
        SYSTEM = "SYSTEM", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    broadcast = models.ForeignKey(
        "notifications.Broadcast", on_delete=models.PROTECT, null=True, blank=True, related_name="notifications",
        help_text="Set when the notification came from an officer's message to many members.",
    )
    category = models.CharField(max_length=15, choices=Category.choices, default=Category.SYSTEM)
    title = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=255, blank=True, help_text="Portal route, e.g. /member/loans/<id>.")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        permissions = [("send_notifications", "Send notifications to members")]
        indexes = [models.Index(fields=["recipient", "read_at"], name="notifications_unread")]

    def __str__(self):
        return f"{self.title} → {self.recipient}"

    @property
    def is_read(self):
        return self.read_at is not None


class Broadcast(TimeStampedModel):
    """
    An officer's message to many members at once. Each recipient gets their own
    Notification; this row is the sent-items record (who, to whom, how many).
    """

    class Audience(models.TextChoices):
        ALL_ACTIVE = "ALL_ACTIVE", "All active members"
        DEPARTMENT = "DEPARTMENT", "Active members of a department"
        SELECTED = "SELECTED", "Selected members"

    title = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    audience = models.CharField(max_length=15, choices=Audience.choices)
    department = models.ForeignKey("configuration.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    recipient_count = models.PositiveIntegerField(default=0)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        default_permissions = ()  # governed by notifications.send_notifications

    def __str__(self):
        return self.title


class Announcement(TimeStampedModel):
    """Cooperative-wide notice shown on portal dashboards."""

    class Audience(models.TextChoices):
        ALL_MEMBERS = "ALL_MEMBERS", "All members"
        OFFICERS = "OFFICERS", "Officers only"
        EVERYONE = "EVERYONE", "Everyone"

    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=15, choices=Audience.choices, default=Audience.ALL_MEMBERS)
    is_important = models.BooleanField(default=False)
    publish_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta(TimeStampedModel.Meta):
        ordering = ["-is_important", "-publish_at"]
        permissions = [("manage_announcements", "Publish announcements")]
        indexes = [models.Index(fields=["audience", "publish_at"], name="notifications_announce_live")]
        constraints = [
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(expires_at__gt=F("publish_at")),
                name="announcement_expires_after_publish",
            ),
        ]

    def __str__(self):
        return self.title
