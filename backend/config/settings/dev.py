import sys

from .base import *  # noqa: F401,F403
from .base import env, env_list

DEBUG = True
SECRET_KEY = env("SECRET_KEY") or "dev-only-insecure-key-do-not-use-in-production"
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS or ["http://localhost:5173"]  # noqa: F405
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS or CORS_ALLOWED_ORIGINS  # noqa: F405

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# The console e-mail backend prints messages (with "₦") to stdout; Windows consoles
# default to a legacy code page that cannot encode it.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REFRESH_COOKIE = {**REFRESH_COOKIE, "SECURE": False}  # noqa: F405 (http://localhost)
