import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-that-is-long-enough-for-hs256"
ALLOWED_HOSTS = ["testserver", "localhost"]
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405 (no collected static in tests)
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"login": "1000/min", "login_ip": "1000/min", "password_reset": "1000/min", "guarantor_lookup": "1000/min"},
}
REFRESH_COOKIE = {**REFRESH_COOKIE, "SECURE": False}  # noqa: F405
FRONTEND_URL = "http://testserver"
ACCOUNT_ACTIVATION_URL = FRONTEND_URL + "/activate?uid={uid}&token={token}"
PASSWORD_RESET_URL = FRONTEND_URL + "/reset-password?uid={uid}&token={token}"
MEDIA_ROOT = Path(tempfile.gettempdir()) / "emdi-coop-test-media"
