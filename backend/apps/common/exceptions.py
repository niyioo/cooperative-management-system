"""
Error handling for the API.

Every error response has the same shape:

    {"error": {"code": "invalid_credentials", "message": "…", "fields": {…}}}

`code` is stable and machine-readable (the frontend branches on it), `message`
is safe to show to users, and `fields` maps field names to messages for
validation errors.
"""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """
    A business rule refused the operation. Raised by services; rendered as 400
    (or `status_code`). The message is shown to the user, so keep it plain.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "business_rule"

    def __init__(self, message, *, code=None, fields=None):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.fields = fields or {}


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


def envelope(code, message, fields=None):
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def _django_validation_detail(exc):
    if hasattr(exc, "error_dict"):
        return exc.message_dict
    return {"non_field_errors": exc.messages}


def _first_message(fields):
    for value in fields.values() if isinstance(fields, dict) else [fields]:
        if isinstance(value, (list, tuple)) and value:
            first = value[0]
            return _first_message(first) if isinstance(first, dict) else str(first)
        if isinstance(value, dict):
            return _first_message(value)
        if value:
            return str(value)
    return "Please correct the highlighted fields."


def _code_of(exc, data):
    if isinstance(data, dict) and isinstance(data.get("code"), str):
        return data["code"]
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, DjangoPermissionDenied):
        return "permission_denied"
    if isinstance(exc, exceptions.APIException):
        codes = exc.get_codes()
        if isinstance(codes, str):
            return codes
        if isinstance(codes, dict) and isinstance(codes.get("detail"), str):
            return codes["detail"]
    return "error"


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(envelope(exc.code, exc.message, exc.fields), status=exc.status_code)

    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(_django_validation_detail(exc))

    if isinstance(exc, IntegrityError):
        # Constraint or trigger violation that validation did not catch first.
        logger.warning("Integrity error in %s: %s", context.get("view"), exc)
        return Response(
            envelope("integrity_error", "This change conflicts with existing records and was not saved."),
            status=status.HTTP_409_CONFLICT,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if response.status_code == status.HTTP_403_FORBIDDEN:
        _record_access_denied(context, _code_of(exc, response.data))

    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        fields = data if isinstance(data, dict) else {"non_field_errors": data}
        response.data = envelope("validation_error", _first_message(fields), fields)
    else:
        detail = data.get("detail", "") if isinstance(data, dict) else data
        response.data = envelope(_code_of(exc, data), str(detail))
    return response


def _record_access_denied(context, code):
    """
    Refused requests by signed-in users are a security signal (e.g. a member
    probing officer endpoints), so they go to the audit log. Logging must never
    mask the original error.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return
    try:
        from apps.audit.services import record

        record(
            "security.access_denied",
            actor=user,
            metadata={"method": request.method, "path": request.path[:255], "code": code},
        )
    except Exception:  # noqa: BLE001
        logger.exception("Could not record an access-denied event")
