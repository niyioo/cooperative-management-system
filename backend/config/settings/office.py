"""
Office installation: the whole system on one computer, used by browsers on the
office network over plain http (see deploy/office/README.md).

Production settings, except that cookies cannot be marked "secure" and nothing
redirects to https, because the office network has no certificate. Moving
online later means switching to the prod settings behind https.
"""
from .prod import *  # noqa: F401,F403
from .prod import REFRESH_COOKIE, env

SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
REFRESH_COOKIE = {**REFRESH_COOKIE, "SECURE": False}
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008", "security.W012", "security.W016", "security.W021"]

# nginx sits in front, so the visitor's address is one proxy back (throttling, audit log).
NUM_PROXIES = int(env("NUM_PROXIES", "1"))
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": NUM_PROXIES or None}  # noqa: F405

# Records brought over from another installation may sit in their own schema.
_schema = env("DB_SCHEMA")
if _schema:
    DATABASES["default"].setdefault("OPTIONS", {})["options"] = f"-c search_path={_schema}"  # noqa: F405
