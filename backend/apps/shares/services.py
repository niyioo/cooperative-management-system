from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.permissions import FINANCE_STAFF
from apps.core.models import SystemSetting
from apps.core.notifications import notify

from .models import ShareAccount, ShareTransaction

Status = ShareTransaction.Status


def unit_price():
    settings = SystemSetting.current()
    if settings is None or not settings.share_unit_price:
        raise ValidationError({"detail": "The share price has not been set. Ask a manager to set it in Settings."})
    return settings.share_unit_price


def _apply(account, txn):
    account.total_shares += txn.number_of_shares
    account.current_value += txn.total_amount
    account.save(update_fields=["total_shares", "current_value", "updated_at"])


@transaction.atomic
def purchase(*, member, number_of_shares, by) -> ShareTransaction:
    """A purchase at the current unit price: applied at once by finance staff, otherwise a request."""
    if number_of_shares < 1:
        raise ValidationError({"number_of_shares": "Buy at least one share."})
    account, _ = ShareAccount.objects.get_or_create(member=member)
    account = ShareAccount.objects.select_for_update().get(pk=account.pk)
    staff = by.role in FINANCE_STAFF
    txn = ShareTransaction.objects.create(
        account=account, number_of_shares=number_of_shares, price_per_share=unit_price(),
        status=Status.APPROVED if staff else Status.PENDING, approved_by=by if staff else None,
    )
    if staff:
        _apply(account, txn)
    return txn


@transaction.atomic
def approve(txn, *, by) -> ShareTransaction:
    txn = ShareTransaction.objects.select_for_update().get(pk=txn.pk)
    if txn.status != Status.PENDING:
        raise ValidationError({"detail": "Only pending share purchases can be approved."})
    account = ShareAccount.objects.select_for_update().select_related('member__user').get(pk=txn.account_id)
    txn.status, txn.approved_by = Status.APPROVED, by
    txn.save()
    _apply(account, txn)
    notify(account.member.user, "SUCCESS", "Shares approved",
           f"{txn.number_of_shares} share(s) worth ₦{txn.total_amount:,.2f} have been added to your account.")
    return txn


@transaction.atomic
def reject(txn, *, by) -> ShareTransaction:
    txn = ShareTransaction.objects.select_for_update().get(pk=txn.pk)
    if txn.status != Status.PENDING:
        raise ValidationError({"detail": "Only pending share purchases can be rejected."})
    txn.status, txn.approved_by = Status.REJECTED, by
    txn.save()
    notify(txn.account.member.user, "WARNING", "Share purchase declined",
           f"Your request for {txn.number_of_shares} share(s) was declined. Please contact the office for details.")
    return txn
