"""
In-app notifications and announcements.

Workflow services call notify_member() inside their own transaction, so a
notification exists exactly when the change it describes was committed.
Officers send messages (broadcasts) and manage announcements through the
functions below; each is permission-checked and audited.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.perms import P
from apps.accounts.permissions import require_perm
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.members.models import Member, MemberStatus

from .emails import send_notification_email
from .models import Announcement, Broadcast, Notification

Category = Notification.Category

# Member-portal routes used as notification links.
LINKS = {
    "application": "/member/loans/applications/{id}",
    "loan": "/member/loans/{id}",
    "loans": "/member/loans",
    "closure": "/member/closure",
    "dividends": "/member/dividends",
    "savings": "/member/savings",
    "guarantees": "/member/guarantees",
}


def link(name, **ids):
    return LINKS[name].format(**ids)


def naira(amount):
    return f"\u20a6{amount:,.2f}"


def notify(user, *, category, title, body, link="", broadcast=None):
    return Notification.objects.create(recipient=user, category=category, title=title, body=body, link=link, broadcast=broadcast)


def notify_member(member, *, category, title, body, link="", email=False):
    """
    Notify a member through their portal account (every member has one, active or not).
    With email=True a copy is e-mailed once the surrounding transaction commits,
    so nobody is e-mailed about a change that was rolled back.
    """
    if member.user_id is None:
        return None
    notification = notify(member.user, category=category, title=title, body=body, link=link)
    if email:
        user = member.user
        transaction.on_commit(lambda: send_notification_email(user, title=title, body=body, link=link))
    return notification


def notify_members(members, *, category, title, body, link=""):
    rows = [Notification(recipient_id=m.user_id, category=category, title=title, body=body, link=link) for m in members if m.user_id]
    Notification.objects.bulk_create(rows, batch_size=500)
    return len(rows)


# ---------------------------------------------------------------------------
# Broadcast messages
# ---------------------------------------------------------------------------

def _clean(value, field, label):
    value = (value or "").strip()
    if not value:
        raise DomainError(f"{label} is required.", code="required", fields={field: [f"{label} is required."]})
    return value


def broadcast_recipients(*, audience, department=None, members=None):
    if audience == Broadcast.Audience.ALL_ACTIVE:
        return Member.objects.filter(status=MemberStatus.ACTIVE)
    if audience == Broadcast.Audience.DEPARTMENT:
        if department is None:
            raise DomainError("Choose a department.", code="required", fields={"department": ["Choose a department."]})
        return Member.objects.filter(status=MemberStatus.ACTIVE, department=department)
    if not members:
        raise DomainError("Choose at least one member.", code="required", fields={"members": ["Choose at least one member."]})
    # Selected members may be in any status except closed: officers sometimes need to reach suspended members.
    return Member.objects.filter(pk__in=[m.pk for m in members]).exclude(status=MemberStatus.CLOSED)


@transaction.atomic
def send_broadcast(actor, *, title, body, audience, department=None, members=None, link=""):
    require_perm(actor, P.SEND_NOTIFICATIONS)
    title = _clean(title, "title", "A title")
    body = _clean(body, "body", "A message")
    recipients = list(broadcast_recipients(audience=audience, department=department, members=members).only("pk", "user_id"))
    if not recipients:
        raise DomainError("No members match this audience.", code="no_recipients")
    broadcast = Broadcast.objects.create(
        title=title, body=body, link=link, audience=audience, department=department if audience == Broadcast.Audience.DEPARTMENT else None,
        sent_by=actor,
    )
    rows = [
        Notification(recipient_id=m.user_id, category=Category.MESSAGE, title=title, body=body, link=link, broadcast=broadcast)
        for m in recipients if m.user_id
    ]
    Notification.objects.bulk_create(rows, batch_size=500)
    broadcast.recipient_count = len(rows)
    broadcast.save(update_fields=["recipient_count", "updated_at"])
    record("notification.broadcast_sent", actor=actor, obj=broadcast,
           metadata={"audience": audience, "recipients": len(rows), "title": title})
    return broadcast


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------

ANNOUNCEMENT_FIELDS = ("title", "body", "audience", "is_important", "publish_at", "expires_at")


def _validate_announcement(data):
    publish_at = data.get("publish_at")
    expires_at = data.get("expires_at")
    if expires_at and publish_at and expires_at <= publish_at:
        raise DomainError("The end date must be after the publish date.", code="invalid_dates",
                          fields={"expires_at": ["Must be after the publish date."]})


@transaction.atomic
def create_announcement(actor, **data):
    require_perm(actor, P.MANAGE_ANNOUNCEMENTS)
    data = {k: v for k, v in data.items() if k in ANNOUNCEMENT_FIELDS}
    data["title"] = _clean(data.get("title"), "title", "A title")
    data["body"] = _clean(data.get("body"), "body", "The announcement text")
    data["publish_at"] = data.get("publish_at") or timezone.now()
    _validate_announcement(data)
    announcement = Announcement.objects.create(created_by=actor, **data)
    record("announcement.created", actor=actor, obj=announcement, metadata={"audience": announcement.audience})
    return announcement


@transaction.atomic
def update_announcement(actor, announcement, **data):
    require_perm(actor, P.MANAGE_ANNOUNCEMENTS)
    announcement = Announcement.objects.select_for_update().get(pk=announcement.pk)
    changes = {}
    for field in ANNOUNCEMENT_FIELDS:
        if field in data and getattr(announcement, field) != data[field]:
            changes[field] = [str(getattr(announcement, field)), str(data[field])]
            setattr(announcement, field, data[field])
    if "title" in data:
        announcement.title = _clean(announcement.title, "title", "A title")
    if "body" in data:
        announcement.body = _clean(announcement.body, "body", "The announcement text")
    _validate_announcement({"publish_at": announcement.publish_at, "expires_at": announcement.expires_at})
    if changes:
        announcement.save()
        record("announcement.updated", actor=actor, obj=announcement, changes=changes)
    return announcement


@transaction.atomic
def end_announcement(actor, announcement):
    """Take an announcement down now. It stays on record (and in the audit log)."""
    require_perm(actor, P.MANAGE_ANNOUNCEMENTS)
    announcement = Announcement.objects.select_for_update().get(pk=announcement.pk)
    now = timezone.now()
    if announcement.expires_at and announcement.expires_at <= now:
        raise DomainError("This announcement has already ended.", code="already_ended")
    if announcement.publish_at > now:
        # Never shown yet: move both dates so the expiry stays after the publish date.
        announcement.publish_at = now - timedelta(seconds=1)
    announcement.expires_at = now
    announcement.save(update_fields=["publish_at", "expires_at", "updated_at"])
    record("announcement.ended", actor=actor, obj=announcement)
    return announcement
