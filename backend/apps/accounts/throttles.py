from rest_framework.throttling import SimpleRateThrottle


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
