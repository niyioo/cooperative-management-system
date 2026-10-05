from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


def validate_model_field(model, field_name, value):
    """Run a model field's validators (extension, size, file signature…) from a serializer."""
    try:
        for validator in model._meta.get_field(field_name).validators:
            validator(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return value


def money_to_str(data):
    """
    Recursively turn Decimals into strings for JSON responses built from plain
    dicts. DRF's encoder would otherwise send floats, which lose kobo precision.
    """
    if isinstance(data, Decimal):
        return format(data, "f")  # keeps the value's own scale: 5000.00, 12.5000
    if isinstance(data, dict):
        return {k: money_to_str(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [money_to_str(v) for v in data]
    return data


@extend_schema_field({"type": "string", "pattern": r"^\d{4}-\d{2}$", "example": "2026-03"})
class PeriodField(serializers.Field):
    """A month, sent as "2026-03" (or any date in the month); stored as the first day of the month."""

    default_error_messages = {"invalid": "Use a month like 2026-03."}

    def to_internal_value(self, data):
        from .spreadsheets import parse_period

        try:
            return parse_period(data)
        except (ValueError, TypeError):
            self.fail("invalid")

    def to_representation(self, value):
        return value.strftime("%Y-%m") if value else None
