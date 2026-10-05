"""
One-time tokens for account activation and password reset, plus JWT helpers.

Activation/reset tokens are Django's HMAC tokens: they embed the password hash
and last login, so they stop working as soon as they are used. Each type has
its own salt and maximum age.
"""
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken


class _MaxAgeTokenGenerator(PasswordResetTokenGenerator):
    max_age_setting = None

    def check_token(self, user, token):
        if not super().check_token(user, token):
            return False
        try:
            issued = base36_to_int(token.split("-")[0])
        except (ValueError, IndexError):
            return False
        return (self._num_seconds(self._now()) - issued) <= getattr(settings, self.max_age_setting)


class ActivationTokenGenerator(_MaxAgeTokenGenerator):
    key_salt = "apps.accounts.tokens.ActivationTokenGenerator"
    max_age_setting = "ACCOUNT_ACTIVATION_TIMEOUT"


class ResetTokenGenerator(_MaxAgeTokenGenerator):
    key_salt = "apps.accounts.tokens.ResetTokenGenerator"
    max_age_setting = "PASSWORD_RESET_TOKEN_TIMEOUT"


activation_token = ActivationTokenGenerator()
password_reset_token = ResetTokenGenerator()


def encode_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def decode_uid(uidb64):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=pk)
    except (TypeError, ValueError, OverflowError, DjangoValidationError, User.DoesNotExist):
        # DjangoValidationError: the decoded value is not a valid UUID.
        return None


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def issue_tokens(user):
    """Return (access_token_str, refresh_token_str, access_lifetime_seconds)."""
    refresh = RefreshToken.for_user(user)
    lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
    return str(refresh.access_token), str(refresh), lifetime


def set_refresh_cookie(response, refresh):
    cfg = settings.REFRESH_COOKIE
    response.set_cookie(
        cfg["NAME"],
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=cfg["PATH"],
        domain=cfg["DOMAIN"],
        secure=cfg["SECURE"],
        httponly=True,
        samesite=cfg["SAMESITE"],
    )


def clear_refresh_cookie(response):
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(cfg["NAME"], path=cfg["PATH"], domain=cfg["DOMAIN"], samesite=cfg["SAMESITE"])
