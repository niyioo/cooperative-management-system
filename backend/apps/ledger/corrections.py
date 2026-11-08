"""
Corrections (ARCHITECTURE.md D1, BR-17). Posted entries are never edited:

  * A REVERSAL cancels one posted entry in full (opposite side, same account,
    same month). When it posts, the original is flagged REVERSED and the
    owning module's reversal hook runs (e.g. a reopened loan).
  * An ADJUSTMENT moves a savings or investment balance with a mandatory reason.

Both are maker–checker by default, so a second officer approves them.
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.money import to_money

from . import hooks
from .choices import EntrySide, TransactionStatus, TransactionType
from .models import Transaction
from .services import account_field, assert_sufficient_balance, create_entry, lock_account

T = TransactionType

# Entry types that can be reversed on their own. Disbursements, interest
# charges, cycle payouts and dividend payments start chains of dependent
# records (schedules, closed cycles, paid dividends) that a plain reversal
# can't unwind safely, so they are excluded for now.
REVERSIBLE_TYPES = {
    T.SAVINGS_OPENING_BALANCE,
    T.SAVINGS_CONTRIBUTION,
    T.SAVINGS_WITHDRAWAL,
    T.LOAN_REPAYMENT,
    T.INVESTMENT_OPENING_BALANCE,
    T.INVESTMENT_CONTRIBUTION,
    T.INVESTMENT_LIQUIDATION,
    T.ADJUSTMENT,
}


def _reason(reason):
    reason = (reason or "").strip()
    if not reason:
        raise DomainError("Please give a reason.", code="reason_required", fields={"reason": ["Please give a reason."]})
    return reason


def _account_of(entry):
    return entry.savings_account or entry.loan or entry.investment_account


def _opposite(side):
    return EntrySide.DEBIT if side == EntrySide.CREDIT else EntrySide.CREDIT


@transaction.atomic
def reverse_entry(actor, entry, *, reason):
    require_perm(actor, P.REVERSE_TRANSACTION)
    entry = Transaction.objects.select_for_update(of=("self",)).select_related("member").get(pk=entry.pk)
    reason = _reason(reason)
    assert_not_self(actor, entry.member, "reverse transactions for")
    if entry.status != TransactionStatus.POSTED:
        raise DomainError("Only posted entries can be reversed.", code="not_posted")
    if entry.txn_type not in REVERSIBLE_TYPES:
        raise DomainError(f"{entry.get_txn_type_display()} entries cannot be reversed here.", code="not_reversible")
    if entry.external_reference == "UPFRONT-INTEREST":
        raise DomainError("Interest deducted at disbursement cannot be reversed on its own.", code="not_reversible")
    if Transaction.objects.filter(reverses=entry).exists():
        raise DomainError("This entry already has a reversal (pending or posted).", code="already_reversed")

    account = _account_of(entry)
    side = _opposite(entry.entry_side)
    if account is not None:
        account = lock_account(account)
        if side == EntrySide.DEBIT and not entry.loan_id:
            # Reversing a credit takes the money back out: the account must still hold it.
            assert_sufficient_balance(account, entry.amount)

    reversal = create_entry(
        actor,
        member=entry.member,
        txn_type=T.REVERSAL,
        entry_side=side,
        amount=entry.amount,
        account=account,
        period=entry.period,
        description=f"Reversal of {entry.reference}: {reason}"[:255],
        reverses=entry,
        audit=False,
    )
    record(
        "ledger.reversal_created",
        actor=actor,
        obj=entry,
        metadata={"reversal": reversal.reference, "reason": reason, "status": reversal.status},
    )
    return reversal


@hooks.on_posted(T.REVERSAL)
def _flag_original(reversal):
    original = Transaction.objects.select_for_update(of=("self",)).get(pk=reversal.reverses_id)
    original.status = TransactionStatus.REVERSED
    original.save(update_fields=["status", "updated_at"])
    record(
        "ledger.entry_reversed",
        actor=reversal.approved_by or reversal.created_by,
        obj=original,
        metadata={"reversal": reversal.reference},
    )
    hooks.run_reversed(original)


@transaction.atomic
def post_adjustment(actor, *, account, entry_side, amount, reason, value_date=None, period=None):
    """
    Correct a savings or investment balance. Loans are corrected by reversing
    the wrong repayment and recording the right one, so the instalment
    allocation stays consistent.
    """
    require_perm(actor, P.POST_ADJUSTMENT)
    reason = _reason(reason)
    if account_field(account) == "loan":
        raise DomainError(
            "Loan balances are corrected by reversing and re-recording repayments, not by adjustment.",
            code="adjustment_not_allowed",
        )
    account = lock_account(account)
    assert_not_self(actor, account.member, "adjust accounts for")
    amount = to_money(amount)
    if entry_side == EntrySide.DEBIT:
        assert_sufficient_balance(account, amount)
    entry = create_entry(
        actor,
        member=account.member,
        txn_type=T.ADJUSTMENT,
        entry_side=entry_side,
        amount=amount,
        account=account,
        value_date=value_date or timezone.localdate(),
        period=period,
        description=reason[:255],
        audit=False,
    )
    record("ledger.adjustment_created", actor=actor, obj=entry, metadata={"side": entry_side, "amount": amount, "reason": reason, "status": entry.status})
    return entry
