import json

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder

from apps.common.middleware import get_request_context

from .models import AuditLog


def _jsonable(value):
    """Decimals, dates and UUIDs become strings so they store cleanly in JSONB."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def record(action, *, actor=None, obj=None, changes=None, metadata=None, object_repr=None):
    """
    Append an audit event. Call it inside the same transaction as the change
    it describes, so the event and the change commit (or roll back) together.

    action   dotted event name, e.g. "loan.approved"
    changes  {field: [old, new]}
    metadata any other context (never passwords, tokens or secrets)
    """
    context = get_request_context()
    authenticated = actor is not None and getattr(actor, "is_authenticated", False)
    return AuditLog.objects.create(
        actor=actor if authenticated else None,
        actor_repr=actor.email if authenticated else "",
        action=action,
        object_type=ContentType.objects.get_for_model(obj, for_concrete_model=False) if obj is not None else None,
        object_id=str(obj.pk) if obj is not None else "",
        object_repr=(object_repr or str(obj))[:255] if obj is not None else (object_repr or "")[:255],
        changes=_jsonable(changes or {}),
        metadata=_jsonable(metadata or {}),
        ip_address=context.ip_address if context else None,
        user_agent=context.user_agent if context else "",
        request_id=context.request_id if context else "",
    )
