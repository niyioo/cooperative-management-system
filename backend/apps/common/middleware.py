"""
Per-request context (client IP, user agent, request ID) available anywhere in
the call stack, mainly for the audit log. Uses a contextvar so it is safe under
threads and async.
"""
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass

from django.conf import settings

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None
    user_agent: str
    request_id: str


_current: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_request_context():
    return _current.get()


def client_ip(request):
    """Client IP, trusting only the configured number of reverse proxies (same rule as DRF throttling)."""
    num_proxies = getattr(settings, "NUM_PROXIES", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies and forwarded:
        addresses = [a.strip() for a in forwarded.split(",") if a.strip()]
        if addresses:
            return addresses[-min(num_proxies, len(addresses))]
    return request.META.get("REMOTE_ADDR")


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        context = RequestContext(
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
            request_id=incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex,
        )
        token = _current.set(context)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = context.request_id
            return response
        finally:
            _current.reset(token)


class NoStoreAPIMiddleware:
    """
    API responses carry access tokens and members' financial records, so no
    browser, proxy or shared cache may keep a copy of them.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
            response["Pragma"] = "no-cache"
        return response
