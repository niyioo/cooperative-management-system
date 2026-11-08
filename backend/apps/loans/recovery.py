"""
Recovering what a borrower owes from their own savings (BR-36).

When repayments fall behind, an officer can take the amount owed from the
member's savings and pay it into the loan. Both entries go into one
LOAN_RECOVERY batch, so they post or fail together, and a second officer
approves it. Recovery is a deliberate decision, so it works even on products
that do not allow everyday withdrawals (Regular Savings included).
"""
from django.db import transaction

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.money import to_money
from apps.common.serializers import money_to_str
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchStatus, BatchType, TransactionStatus, TransactionType
from apps.ledger.models import TransactionBatch
from apps.notifications import services as notifications
from apps.savings.models import ProductKind, SavingsAccount

from .models import Loan
from .selectors import loan_arrears
from .services import repayable


def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


def open_recovery_batch(loan):
    return TransactionBatch.objects.filter(
        batch_type=BatchType.LOAN_RECOVERY,
        status__in=[BatchStatus.VALIDATED, BatchStatus.SUBMITTED],
        validation_report__loan_id=str(loan.pk),
    ).first()


def recoverable_accounts(loan):
    """The borrower's active savings accounts that can be drawn on (Christmas-type cycle savings are paid out by their cycle)."""
    return (
        SavingsAccount.objects.filter(member=loan.member, status=SavingsAccount.Status.ACTIVE)
        .exclude(product__kind=ProductKind.CYCLE)
        .select_related("product")
        .order_by("-product__is_mandatory", "product__name")
    )


def available(account):
    return ledger.posted_balance(account) - ledger.pending_debits(account)


def recovery_options(loan):
    """What the recovery form needs: what is owed, what is overdue, and what each account could give."""
    arrears = loan_arrears(loan)
    return money_to_str(
        {
            "outstanding": repayable(loan),
            "arrears": arrears["amount"],
            "days_overdue": arrears["days_overdue"],
            "pending_batch": getattr(open_recovery_batch(loan), "reference", None),
            "accounts": [
                {"id": str(a.pk), "product_name": a.product.name, "account_number": a.account_number, "available": available(a)}
                for a in recoverable_accounts(loan)
            ],
        }
    )


@transaction.atomic
def recover_from_savings(actor, loan, *, savings_account, amount, reason, value_date=None):
    require_perm(actor, P.RECORD_LOAN_REPAYMENT, P.POST_SAVINGS_WITHDRAWAL, P.MANAGE_BATCHES)
    loan = ledger.lock_account(loan)
    assert_not_self(actor, loan.member, "recover loans of")
    if loan.status not in Loan.RUNNING_STATUSES:
        raise DomainError(f"This loan is {loan.get_status_display().lower()}.", code="loan_not_running")
    if open_recovery_batch(loan):
        raise DomainError("A recovery for this loan is already awaiting approval.", code="recovery_in_progress")
    if savings_account.member_id != loan.member_id:
        _field_error("savings_account", "The savings account must belong to the borrower.", "wrong_member")
    if not recoverable_accounts(loan).filter(pk=savings_account.pk).exists():
        _field_error("savings_account", "Money cannot be recovered from this account.", "account_not_recoverable")
    if not (reason or "").strip():
        _field_error("reason", "Please give a reason.", "reason_required")
    amount = to_money(amount)
    if amount <= 0:
        _field_error("amount", "Enter an amount above zero.", "invalid_amount")
    owed = repayable(loan)
    if amount > owed:
        _field_error("amount", f"The loan only has ₦{owed:,.2f} left to pay.", "overpayment")
    savings_account = ledger.lock_account(savings_account)
    holds = available(savings_account)
    if amount > holds:
        _field_error("amount", f"{savings_account.product.name} has only ₦{holds:,.2f} available.", "insufficient_balance")

    member, reason = loan.member, reason.strip()

    def build(batch):
        batch.validation_report = {"loan_id": str(loan.pk), "reason": reason}
        common = dict(member=member, amount=amount, value_date=value_date, batch=batch, audit=False)
        ledger.create_entry(actor, txn_type=TransactionType.SAVINGS_WITHDRAWAL, account=savings_account,
                            description=f"Recovered for loan {loan.reference}: {reason}", **common)
        ledger.create_entry(actor, txn_type=TransactionType.LOAN_REPAYMENT, account=loan,
                            description=f"Recovered from {savings_account.product.name}: {reason}", **common)

    batch = ledger.create_batch_from_entries(
        actor, batch_type=BatchType.LOAN_RECOVERY, build_lines=build,
        description=f"Recover ₦{amount:,.2f} for {loan.reference} from {savings_account.product.name}",
    )
    record("loan.recovery_prepared", actor=actor, obj=loan,
           metadata=money_to_str({"batch": batch.reference, "amount": amount, "account": savings_account.account_number, "reason": reason}))
    return batch


class LoanRecoveryBatchHandler(BatchHandler):
    """Built by recover_from_savings(); no file upload."""

    batch_type = BatchType.LOAN_RECOVERY
    permissions = (P.RECORD_LOAN_REPAYMENT, P.POST_SAVINGS_WITHDRAWAL)
    accepts_files = False

    def revalidate(self, batch):
        problems = []
        for entry in batch.transactions.filter(status=TransactionStatus.PENDING).select_related("savings_account", "loan", "member"):
            if entry.savings_account_id and entry.amount > ledger.posted_balance(entry.savings_account):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"{entry.savings_account} no longer holds ₦{entry.amount:,.2f}."]})
            if entry.loan_id and entry.amount > -ledger.posted_balance(entry.loan):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"{entry.loan.reference} now owes less than ₦{entry.amount:,.2f}."]})
        return problems

    def after_post(self, batch):
        entry = batch.transactions.filter(loan__isnull=False).select_related("loan", "member").first()
        record("loan.recovered", actor=batch.approved_by, obj=entry.loan,
               metadata=money_to_str({"batch": batch.reference, "amount": entry.amount}))
        notifications.notify_member(
            entry.member, category=notifications.Category.LOAN,
            title="Loan repayment taken from your savings",
            body=f"{notifications.naira(entry.amount)} was taken from your savings and paid into loan {entry.loan.reference}. "
                 f"Reason: {batch.validation_report.get('reason', '')}",
            link=notifications.link("loan", id=entry.loan_id), email=True,
        )
