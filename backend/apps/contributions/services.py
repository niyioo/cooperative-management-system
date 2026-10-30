from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.notifications import notify
from apps.finance import services as ledger
from apps.finance.models import LedgerEntry

from .models import Contribution


@transaction.atomic
def assess(*, member, type, amount, due_date, by) -> Contribution:
    if amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})
    contribution = Contribution.objects.create(member=member, type=type, amount=amount, due_date=due_date)
    notify(member.user, "INFO", f"New {contribution.get_type_display().lower()}",
           f"₦{amount:,.2f} is due" + (f" by {due_date:%d %b %Y}." if due_date else "."))
    return contribution


@transaction.atomic
def mark_paid(contribution, *, by) -> Contribution:
    """Record payment once, and the matching income in the ledger."""
    contribution = Contribution.objects.select_for_update().select_related('member').get(pk=contribution.pk)
    if contribution.status == Contribution.StatusChoices.PAID:
        raise ValidationError({"detail": "This assessment is already marked as paid."})
    contribution.status = Contribution.StatusChoices.PAID
    contribution.received_by = by
    contribution.date_paid = timezone.localdate()
    contribution.save(update_fields=["status", "received_by", "date_paid", "updated_at"])
    ledger.record(
        type=LedgerEntry.EntryType.INCOME, category=contribution.get_type_display(), amount=contribution.amount,
        member=contribution.member, recorded_by=by,
        description=f"{contribution.get_type_display()} {contribution.reference_id} paid",
    )
    return contribution
