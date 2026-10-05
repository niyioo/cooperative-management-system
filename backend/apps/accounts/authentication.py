"""JWT authentication that also ends sessions started before the last password change."""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class PasswordAwareJWTAuthentication(JWTAuthentication):
    """
    Refresh tokens are revoked when a password changes, but an access token
    already handed out would otherwise keep working until it expires. Reject
    any access token issued before the password was last changed, so a reset
    after a suspected compromise takes effect at once.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        changed = user.last_password_change
        issued = validated_token.get("iat")
        if changed and issued is not None and int(issued) < int(changed.timestamp()):
            raise AuthenticationFailed("Your password was changed. Please sign in again.", code="password_changed")
        return user


try:  # Describe it in the OpenAPI schema exactly like the stock JWT scheme.
    from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme

    class PasswordAwareJWTScheme(SimpleJWTScheme):
        target_class = "apps.accounts.authentication.PasswordAwareJWTAuthentication"
except ImportError:  # pragma: no cover - drf-spectacular is a hard dependency
    pass
