from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import NumberSequence


def next_value(key: str) -> int:
    """Atomically increment and return the counter for `key`, creating it on first use."""
    with transaction.atomic():
        updated = NumberSequence.objects.filter(key=key).update(last_value=F("last_value") + 1)
        if not updated:
            try:
                with transaction.atomic():
                    NumberSequence.objects.create(key=key, last_value=1)
                return 1
            except IntegrityError:
                # Another transaction created the row first; increment it instead.
                NumberSequence.objects.filter(key=key).update(last_value=F("last_value") + 1)
        return NumberSequence.objects.values_list("last_value", flat=True).get(key=key)


def generate_reference(prefix: str, *, width: int = 4, year: int | None = None) -> str:
    """Return e.g. 'LN-2026-0042'. Counters restart every year."""
    year = year or timezone.localdate().year
    value = next_value(f"{prefix}-{year}")
    return f"{prefix}-{year}-{value:0{width}d}"
