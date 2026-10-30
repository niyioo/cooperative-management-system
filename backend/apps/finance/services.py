"""The cooperative ledger. Every money movement elsewhere records its entry through here."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import LedgerEntry


def record(*, type, category, amount, description, member=None, recorded_by=None, date=None) -> LedgerEntry:
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})
    return LedgerEntry.objects.create(
        type=type, category=category, amount=amount, description=description,
        member=member, recorded_by=recorded_by, date=date or timezone.localdate(),
    )


@transaction.atomic
def reverse(entry: LedgerEntry, *, by, reason: str) -> LedgerEntry:
    """Cancel an entry by recording its opposite. The original stays on the books."""
    entry = LedgerEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.reverses_id:
        raise ValidationError({"detail": "A reversing entry cannot itself be reversed."})
    if hasattr(entry, "reversed_by"):
        raise ValidationError({"detail": "This entry has already been reversed."})
    opposite = LedgerEntry.EntryType.EXPENSE if entry.type == LedgerEntry.EntryType.INCOME else LedgerEntry.EntryType.INCOME
    reversal = record(
        type=opposite, category=entry.category, amount=entry.amount, member=entry.member, recorded_by=by,
        description=f"Reversal of {entry.reference_id}: {reason}",
    )
    reversal.reverses = entry
    reversal.save(update_fields=["reverses"])
    return reversal
