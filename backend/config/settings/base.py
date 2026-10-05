"""
Base settings shared by every environment.

All secrets and deployment-specific values come from environment variables
(loaded from backend/.env in development). See /.env.example for the full list.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Environment variable {name} is required.")
    return value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # EMDI Cooperative
    "apps.common",
    "apps.accounts",
    "apps.configuration",
    "apps.audit",
    "apps.members",
    "apps.savings",
    "apps.loans",
    "apps.investments",
    "apps.dividends",
    "apps.ledger",
    "apps.closures",
    "apps.notifications",
    "apps.reports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.RequestContextMiddleware",
    "apps.common.middleware.NoStoreAPIMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Database (PostgreSQL only — the schema relies on PostgreSQL features)
# --------------------------------------------------------------------------
if env("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            env("DATABASE_URL"), conn_max_age=600, conn_health_checks=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "emdi_coop"),
            "USER": env("DB_USER", "emdi_coop"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# Log in with an email address or a membership number.
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrMembershipNumberBackend"]

# Token lifetimes. PASSWORD_RESET_TIMEOUT is Django's outer limit; each token
# type then applies its own stricter maximum (apps.accounts.tokens).
ACCOUNT_ACTIVATION_TIMEOUT = int(env("ACCOUNT_ACTIVATION_TIMEOUT_HOURS", "72")) * 3600
PASSWORD_RESET_TOKEN_TIMEOUT = int(env("PASSWORD_RESET_TIMEOUT_MINUTES", "60")) * 60
PASSWORD_RESET_TIMEOUT = max(ACCOUNT_ACTIVATION_TIMEOUT, PASSWORD_RESET_TOKEN_TIMEOUT)

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalisation — month boundaries for contributions follow Lagos time
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-ng"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static & media
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media holds member photos and documents. It is never served publicly in
# production; files are streamed through permission-checked API views.
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_MANIFEST_STRICT = False

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
# Number of trusted reverse proxies in front of the app (e.g. 1 on Render).
# Used for client IPs in throttling and the audit log.
NUM_PROXIES = int(env("NUM_PROXIES", "0"))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.PasswordAwareJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # JSON only by default. Form encodings send a missing boolean as False, which
    # could silently flip flags; the few file-upload endpoints opt in to multipart.
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    # Every request counts against a per-user (or, signed out, per-address) limit;
    # login, password reset/change and guarantor lookups have tighter limits of their own.
    "DEFAULT_THROTTLE_CLASSES": (
        "apps.accounts.throttles.APIAnonRateThrottle",
        "apps.accounts.throttles.APIUserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": env("API_RATE_USER", "600/min"),
        "anon": env("API_RATE_ANON", "60/min"),
        "password_change": "5/min",  # per user
        "login": "5/min",  # per IP + identifier
        "login_ip": "30/min",  # per IP, across identifiers
        "password_reset": "5/hour",
        "guarantor_lookup": "30/hour",  # membership-number lookups, per member
    },
    "NUM_PROXIES": NUM_PROXIES or None,
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
    # ?format= is ours (statements and reports: pdf/xlsx), not DRF's renderer override.
    "URL_FORMAT_OVERRIDE": None,
    "DATETIME_FORMAT": "iso-8601",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # Tokens carry a hash of the password hash, so changing a password
    # invalidates every existing access and refresh token immediately.
    "CHECK_REVOKE_TOKEN": True,
}

# The refresh token never reaches JavaScript: it lives in an httpOnly cookie
# scoped to the auth endpoints. SameSite=None is only needed when the SPA and
# API are on different sites (requires Secure).
REFRESH_COOKIE = {
    "NAME": env("REFRESH_COOKIE_NAME", "emdi_refresh"),
    "PATH": "/api/v1/auth/",
    "DOMAIN": env("REFRESH_COOKIE_DOMAIN") or None,
    "SECURE": env_bool("REFRESH_COOKIE_SECURE", not DEBUG),
    "SAMESITE": env("REFRESH_COOKIE_SAMESITE", "Lax"),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "EMDI Cooperative Management System API",
    "DESCRIPTION": "Officer portal (/admin), member self-service (/me) and authentication (/auth).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    # Several models have a "status" field with different choices; name each explicitly.
    "ENUM_NAME_OVERRIDES": {
        "MemberStatusEnum": "apps.members.models.MemberStatus",
        "MemberInitialStatusEnum": [("PENDING", "Pending activation"), ("ACTIVE", "Active")],
        "MemberImportStatusEnum": "apps.members.models.MemberImport.Status",
        "TransactionStatusEnum": "apps.ledger.choices.TransactionStatus",
        "TransactionTypeEnum": "apps.ledger.choices.TransactionType",
        "EntrySideEnum": "apps.ledger.choices.EntrySide",
        "BatchStatusEnum": "apps.ledger.choices.BatchStatus",
        "SavingsCycleStatusEnum": "apps.savings.models.SavingsCycle.Status",
        "SavingsAccountStatusEnum": "apps.savings.models.SavingsAccount.Status",
        "LoanStatusEnum": "apps.loans.models.Loan.Status",
        "LoanApplicationStatusEnum": "apps.loans.models.LoanApplication.Status",
        "GuarantorStatusEnum": "apps.loans.models.LoanGuarantor.Status",
        "ClosureStatusEnum": "apps.closures.models.AccountClosureRequest.Status",
        "AnnouncementAudienceEnum": "apps.notifications.models.Announcement.Audience",
        "BroadcastAudienceEnum": "apps.notifications.models.Broadcast.Audience",
    },
}

# --------------------------------------------------------------------------
# CORS / CSRF
# --------------------------------------------------------------------------
# CORS_ALLOWED_ORIGIN (singular) is accepted for backwards compatibility.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS") or env_list("CORS_ALLOWED_ORIGIN")
CORS_ALLOW_CREDENTIALS = True
# Lets the SPA read download file names (statements, exports) cross-origin.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") or CORS_ALLOWED_ORIGINS

# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "EMDI Cooperative <no-reply@localhost>")

# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------
DJANGO_ADMIN_URL = env("DJANGO_ADMIN_URL", "django-admin/")
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173").rstrip("/")
# Links in activation and password-reset emails. With the SPA's hash router,
# set FRONTEND_URL to include the "#" (e.g. https://host/app/#).
ACCOUNT_ACTIVATION_URL = env("ACCOUNT_ACTIVATION_URL", FRONTEND_URL + "/activate?uid={uid}&token={token}")
PASSWORD_RESET_URL = env("PASSWORD_RESET_URL", FRONTEND_URL + "/reset-password?uid={uid}&token={token}")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}

JAZZMIN_SETTINGS = {
    "site_title": "EMDI Cooperative",
    "site_header": "EMDI Cooperative",
    "site_brand": "EMDI Cooperative",
    "welcome_sign": "Restricted — Super Administrator support console",
    "copyright": "EMDI Cooperative Society",
    "show_ui_builder": False,
}
