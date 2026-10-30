"""
The refresh token lives only in an httpOnly cookie scoped to the auth endpoints,
so page scripts (and anything injected into the page) can never read it.
"""
from django.conf import settings
from rest_framework.exceptions import UnsupportedMediaType


def _cfg():
    return settings.AUTH_COOKIE


def set_refresh_cookie(response, token):
    cfg = _cfg()
    response.set_cookie(
        cfg['NAME'], token, max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
        path=cfg['PATH'], secure=cfg['SECURE'], httponly=True, samesite=cfg['SAMESITE'],
    )


def clear_refresh_cookie(response):
    cfg = _cfg()
    response.delete_cookie(cfg['NAME'], path=cfg['PATH'], samesite=cfg['SAMESITE'])


def get_refresh_cookie(request):
    return request.COOKIES.get(_cfg()['NAME'])


def require_json(request):
    """
    Cookie-authenticated endpoints only accept JSON bodies. A cross-site form
    can't send JSON without a CORS preflight, which the allow-list refuses, so
    this blocks cross-site request forgery against refresh and logout.
    """
    if not (request.content_type or '').startswith('application/json'):
        raise UnsupportedMediaType(request.content_type or 'none')
