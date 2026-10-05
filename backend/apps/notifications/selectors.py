from django.db.models import Q
from django.utils import timezone

from .models import Announcement


def visible_announcements(*, for_officers=False):
    """Announcements that are published, not expired, and meant for this audience."""
    now = timezone.now()
    audiences = [Announcement.Audience.EVERYONE, Announcement.Audience.OFFICERS if for_officers else Announcement.Audience.ALL_MEMBERS]
    return (
        Announcement.objects.filter(audience__in=audiences, publish_at__lte=now)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-is_important", "-publish_at")
    )
