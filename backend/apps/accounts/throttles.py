from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    """Limits guesses against one account from one address."""

    scope = "login"

    def get_cache_key(self, request, view):
        identifier = str(request.data.get("identifier", "")).strip().lower()[:254]
        return self.cache_format % {"scope": self.scope, "ident": f"{self.get_ident(request)}:{identifier}"}


class LoginIPRateThrottle(SimpleRateThrottle):
    """Limits spraying many accounts from one address."""

    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PasswordResetRateThrottle(SimpleRateThrottle):
    scope = "password_reset"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class APIUserRateThrottle(UserRateThrottle):
    """Default limit for every signed-in request (all endpoints together), per user."""


class APIAnonRateThrottle(AnonRateThrottle):
    """Default limit for unauthenticated requests, per address."""


class PasswordChangeRateThrottle(UserRateThrottle):
    """Limits guesses at the current password by someone holding a stolen access token."""

    scope = "password_change"
