"""
Append-only audit trail (ARCHITECTURE.md D11). Answers who did what, when,
from where, and what changed. A PostgreSQL trigger (migration 0002) rejects
UPDATE and DELETE on this table.
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Null for system jobs and anonymous events such as failed logins.",
    )
    actor_repr = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=80, help_text="Dotted event name, e.g. loan.approved.")
    object_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True, help_text="{field: [old, new]}")
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        default_permissions = ()
        permissions = [("view_audit_log", "View the audit log")]
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["object_type", "object_id"], name="audit_log_object"),
            models.Index(fields=["actor", "timestamp"], name="audit_log_actor"),
            models.Index(fields=["action", "timestamp"], name="audit_log_action"),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor_repr or 'system'} {self.action}"
