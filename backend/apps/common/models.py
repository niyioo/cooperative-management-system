import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """
    Base for every domain model: UUID primary key plus creation/update timestamps.

    Default Django permissions (add/change/delete/view) are disabled; each app
    declares its own permission catalogue (see docs/ARCHITECTURE.md §3), so the
    role editor only shows permissions that mean something to officers.
    Subclasses declare `class Meta(TimeStampedModel.Meta)` to keep this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        default_permissions = ()


class ReferenceMixin:
    """
    Fills a human-readable `reference` field (e.g. LN-2026-0042) from a locked
    NumberSequence on first save. Subclasses set REFERENCE_PREFIX and may set
    REFERENCE_WIDTH or override build_reference().
    """

    REFERENCE_PREFIX = None
    REFERENCE_WIDTH = 4

    def build_reference(self):
        from .sequences import generate_reference

        return generate_reference(self.REFERENCE_PREFIX, width=self.REFERENCE_WIDTH)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.build_reference()
        super().save(*args, **kwargs)


class NumberSequence(models.Model):
    """
    Counters for references and membership numbers. Always incremented through
    apps.common.sequences.next_value(), which holds a row lock, so concurrent
    requests never receive the same number.
    """

    key = models.CharField(max_length=50, unique=True)
    last_value = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"{self.key}: {self.last_value}"
