"""
Savings money movements. This is the only code that changes a savings balance.

Each change runs in one transaction with the account row locked, so two
deposits or withdrawals at the same moment can never overwrite each other,
and an account can never go below zero.
"""
import uuid
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.permissions import FINANCE_STAFF
from apps.core.notifications import notify

from .models import SavingsAccount, SavingsTransaction

Type = SavingsTransaction.TransactionType
Status = SavingsTransaction.Status
CREDITS = (Type.DEPOSIT, Type.DIVIDEND, Type.INTEREST)
# What a member may ask for themselves; dividends and interest are staff-only.
MEMBER_REQUESTS = (Type.DEPOSIT, Type.WITHDRAWAL)


def _new_reference(prefix="TXN") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def _locked_account(account) -> SavingsAccount:
    return SavingsAccount.objects.select_for_update().get(pk=account.pk)


def _apply(account: SavingsAccount, txn_type, amount: Decimal):
    """Move money on a locked account. Raises (and so rolls back) on overdraft."""
    if txn_type in CREDITS:
        account.balance += amount
    elif txn_type == Type.WITHDRAWAL:
        if account.balance < amount:
            raise ValidationError({"amount": f"Insufficient balance: ₦{account.balance:,.2f} available."})
        account.balance -= amount
    else:
        raise ValidationError({"transaction_type": "Unknown transaction type."})
    account.save(update_fields=["balance", "last_updated"])


def _create(*, account, txn_type, amount, by, description, reference, apply_now) -> SavingsTransaction:
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": "Amount must be greater than zero."})
    account = _locked_account(account)
    if apply_now:
        _apply(account, txn_type, amount)
    return SavingsTransaction.objects.create(
        account=account, transaction_type=txn_type, amount=amount, description=description,
        reference=reference or _new_reference(),
        status=Status.APPROVED if apply_now else Status.PENDING,
        approved_by=by if apply_now else None,
    )


@transaction.atomic
def record(*, account, txn_type, amount, by, description="", reference=None) -> SavingsTransaction:
    """
    Finance staff record a transaction (applied at once); anyone else's request
    waits for approval. Returns the saved transaction.
    """
    staff = by.role in FINANCE_STAFF
    if not staff and txn_type not in MEMBER_REQUESTS:
        raise ValidationError({"transaction_type": "Members can only request deposits and withdrawals."})
    return _create(account=account, txn_type=txn_type, amount=amount, by=by,
                   description=description, reference=reference, apply_now=staff)


@transaction.atomic
def approve(txn: SavingsTransaction, *, by) -> SavingsTransaction:
    txn = SavingsTransaction.objects.select_for_update().get(pk=txn.pk)
    if txn.status != Status.PENDING:
        raise ValidationError({"detail": f"Only pending transactions can be approved (this one is {txn.get_status_display().lower()})."})
    account = _locked_account(txn.account)
    _apply(account, txn.transaction_type, txn.amount)  # raises before anything is saved
    txn.status, txn.approved_by = Status.APPROVED, by
    txn.save(update_fields=["status", "approved_by", "updated_at"])
    notify(account.member.user, "SUCCESS", f"{txn.get_transaction_type_display()} approved",
           f"Your {txn.get_transaction_type_display().lower()} of ₦{txn.amount:,.2f} has been approved.")
    return txn


@transaction.atomic
def reject(txn: SavingsTransaction, *, by, reason: str) -> SavingsTransaction:
    txn = SavingsTransaction.objects.select_for_update().get(pk=txn.pk)
    if txn.status != Status.PENDING:
        raise ValidationError({"detail": "Only pending transactions can be rejected."})
    txn.status, txn.approved_by, txn.rejection_reason = Status.REJECTED, by, reason
    txn.save(update_fields=["status", "approved_by", "rejection_reason", "updated_at"])
    notify(txn.account.member.user, "WARNING", f"{txn.get_transaction_type_display()} declined",
           f"Your request of ₦{txn.amount:,.2f} was declined: {reason}")
    return txn


def credit_from_loan(*, member, amount, by, description) -> SavingsTransaction:
    """Pay a disbursed loan into the member's savings. Called inside the loan's transaction."""
    account, _ = SavingsAccount.objects.get_or_create(member=member)
    return _create(account=account, txn_type=Type.DEPOSIT, amount=amount, by=by,
                   description=description, reference=_new_reference("DISB"), apply_now=True)
