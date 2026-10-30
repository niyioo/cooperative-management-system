"""
The loan lifecycle: PENDING → APPROVED → ACTIVE → COMPLETED (or REJECTED).

Every step runs here, in one transaction with the loan row locked, so the
same loan can never be approved, paid out or repaid twice by two clicks at once.
"""
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.notifications import notify
from apps.finance import services as ledger
from apps.finance.models import LedgerEntry
from apps.savings import services as savings

from .models import Loan, LoanRepayment

Status = Loan.Status


def _locked(loan) -> Loan:
    return Loan.objects.select_for_update().select_related('member__user', 'loan_product').get(pk=loan.pk)


@transaction.atomic
def apply(*, member, product, principal, months, purpose, by) -> Loan:
    principal = Decimal(principal)
    if not product.is_active:
        raise ValidationError({"loan_product_id": "This loan product is no longer offered."})
    if principal <= 0:
        raise ValidationError({"principal_amount": "Enter an amount greater than zero."})
    if principal > product.max_amount:
        raise ValidationError({"principal_amount": f"{product.name} loans are limited to ₦{product.max_amount:,.2f}."})
    if not 1 <= months <= product.max_duration_months:
        raise ValidationError({"duration_months": f"Choose between 1 and {product.max_duration_months} months."})
    loan = Loan.objects.create(member=member, loan_product=product, principal_amount=principal,
                               duration_months=months, purpose=purpose)
    notify(member.user, "INFO", "Loan request received",
           f"Your request for ₦{principal:,.2f} ({product.name}) is being reviewed.")
    return loan


def _require_independent(loan, by):
    # Separation of duties: staff never decide on their own loan.
    if loan.member.user_id == by.pk:
        raise PermissionDenied("You cannot approve, pay out or decide on your own loan.")


@transaction.atomic
def approve(loan, *, by) -> Loan:
    loan = _locked(loan)
    _require_independent(loan, by)
    if loan.status != Status.PENDING:
        raise ValidationError({"detail": "Only pending loans can be approved."})
    loan.status, loan.approved_by = Status.APPROVED, by
    loan.save(update_fields=["status", "approved_by", "updated_at"])
    notify(loan.member.user, "SUCCESS", "Loan approved",
           f"Your loan of ₦{loan.principal_amount:,.2f} has been approved and is awaiting disbursement.")
    return loan


@transaction.atomic
def reject(loan, *, by, reason="") -> Loan:
    loan = _locked(loan)
    _require_independent(loan, by)
    if loan.status != Status.PENDING:
        raise ValidationError({"detail": "Only pending loans can be rejected."})
    loan.status = Status.REJECTED
    loan.save(update_fields=["status", "updated_at"])
    notify(loan.member.user, "WARNING", "Loan not approved",
           f"Your loan request {loan.loan_id} was not approved." + (f" Reason: {reason}" if reason else ""))
    return loan


@transaction.atomic
def disburse(loan, *, by) -> Loan:
    """Pay the principal into the member's savings and record the cash outflow."""
    loan = _locked(loan)
    _require_independent(loan, by)
    if loan.status != Status.APPROVED:
        raise ValidationError({"detail": "Only approved loans can be disbursed."})
    loan.status, loan.disbursed_at, loan.balance_remaining = Status.ACTIVE, timezone.now(), loan.total_payable
    loan.save(update_fields=["status", "disbursed_at", "balance_remaining", "updated_at"])
    savings.credit_from_loan(member=loan.member, amount=loan.principal_amount, by=by,
                             description=f"Loan disbursement for {loan.loan_id}")
    ledger.record(type=LedgerEntry.EntryType.EXPENSE, category="Loan Disbursement", amount=loan.principal_amount,
                  member=loan.member, recorded_by=by, description=f"Principal disbursement for loan {loan.loan_id}")
    notify(loan.member.user, "SUCCESS", "Loan disbursed",
           f"₦{loan.principal_amount:,.2f} from loan {loan.loan_id} has been paid into your savings.")
    return loan


@transaction.atomic
def repay(loan, *, amount, by) -> LoanRepayment:
    """Record a repayment received by staff. Cannot exceed what is still owed."""
    amount = Decimal(amount)
    loan = _locked(loan)
    if loan.status != Status.ACTIVE:
        raise ValidationError({"loan": "Repayments can only be recorded on active loans."})
    if amount <= 0:
        raise ValidationError({"amount_paid": "Enter an amount greater than zero."})
    if amount > loan.balance_remaining:
        raise ValidationError({"amount_paid": f"Only ₦{loan.balance_remaining:,.2f} is still owed on this loan."})

    repayment = LoanRepayment.objects.create(
        loan=loan, amount_paid=amount, received_by=by, receipt_reference=f"REP-{uuid.uuid4().hex[:10].upper()}",
    )
    loan.balance_remaining -= amount
    if loan.balance_remaining == 0:
        loan.status = Status.COMPLETED
    loan.save(update_fields=["balance_remaining", "status", "updated_at"])
    ledger.record(type=LedgerEntry.EntryType.INCOME, category="Loan Repayment", amount=amount,
                  member=loan.member, recorded_by=by, description=f"Repayment received for loan {loan.loan_id}")
    if loan.status == Status.COMPLETED:
        notify(loan.member.user, "SUCCESS", "Loan fully repaid", f"Loan {loan.loan_id} is now fully repaid.")
    return repayment
