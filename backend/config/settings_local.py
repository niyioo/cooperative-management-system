"""Try CoopManager on one machine without PostgreSQL: a SQLite file next to manage.py."""
import os

os.environ.setdefault("DEBUG", "True")

from .settings import *  # noqa: E402,F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "coop-local.sqlite3"}}  # noqa: F405
AUTH_COOKIE = {**AUTH_COOKIE, "SECURE": False}  # noqa: F405
CORS_ALLOWED_ORIGINS = ["http://localhost:5173", "http://localhost:5190"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
