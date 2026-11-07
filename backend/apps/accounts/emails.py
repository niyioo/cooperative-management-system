import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.configuration.models import CooperativeSettings

from .tokens import activation_token, encode_uid, password_reset_token

logger = logging.getLogger(__name__)


def _send(user, subject, body):
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception:
        # Never surface mail failures to the requester (it would reveal whether the account exists).
        logger.exception("Failed to send '%s' email to user %s", subject, user.pk)


def activation_link(user):
    return settings.ACCOUNT_ACTIVATION_URL.format(uid=encode_uid(user), token=activation_token.make_token(user))


def password_reset_link(user):
    return settings.PASSWORD_RESET_URL.format(uid=encode_uid(user), token=password_reset_token.make_token(user))


def send_activation_email(user):
    coop = CooperativeSettings.load().name
    hours = settings.ACCOUNT_ACTIVATION_TIMEOUT // 3600
    body = (
        f"Dear {user.first_name or 'Member'},\n\n"
        f"An account has been created for you on the {coop} portal.\n\n"
        f"Set your password and activate your account here (the link expires in {hours} hours):\n"
        f"{activation_link(user)}\n\n"
        "If you were not expecting this email, please contact the cooperative secretariat.\n\n"
        f"{coop}"
    )
    _send(user, f"Activate your {coop} account", body)


def send_password_reset_email(user):
    coop = CooperativeSettings.load().name
    minutes = settings.PASSWORD_RESET_TOKEN_TIMEOUT // 60
    body = (
        f"Dear {user.first_name or 'Member'},\n\n"
        f"We received a request to reset your {coop} portal password.\n\n"
        f"Choose a new password here (the link expires in {minutes} minutes):\n"
        f"{password_reset_link(user)}\n\n"
        "If you did not request this, you can ignore this email; your password will not change.\n\n"
        f"{coop}"
    )
    _send(user, f"Reset your {coop} password", body)
