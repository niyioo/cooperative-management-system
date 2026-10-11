"""E-mail copies of in-app notifications."""
import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import is_placeholder_email
from apps.configuration.models import CooperativeSettings

logger = logging.getLogger(__name__)


def portal_url(link):
    """Absolute portal URL for an in-app link such as /member/guarantees."""
    return f"{settings.FRONTEND_URL.rstrip('/')}{link}" if link else settings.FRONTEND_URL


def can_email(user):
    return bool(user and user.is_active and user.email and not is_placeholder_email(user.email))


def send_notification_email(user, *, title, body, link=""):
    """Send one notification by e-mail. Failures are logged, never raised: the in-app copy still exists."""
    if not can_email(user):
        return False
    coop = CooperativeSettings.load().name
    text = (
        f"Dear {user.first_name or 'Member'},\n\n"
        f"{body}\n\n"
        + (f"Open the member portal to respond:\n{portal_url(link)}\n\n" if link else "")
        + f"{coop}\n\nThis message was sent by the {coop} portal. You can also see it under Notifications when you sign in."
    )
    try:
        send_mail(f"{coop}: {title}", text, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        return True
    except Exception:
        logger.exception("Failed to e-mail notification '%s' to user %s", title, user.pk)
        return False
