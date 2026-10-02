"""
Account closure (ARCHITECTURE.md §6.4, BR-11/12/24).

Members submit a request and may withdraw it before an officer starts
reviewing it. Submitting changes nothing about the account: officers review,
approve, then execute the closure (settlement batch, second-officer approval).
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.accounts.services import revoke_refresh_tokens
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.serializers import money_to_str
from apps.configuration.models import CooperativeSettings
from apps.dividends.models import MemberDividend
from apps.investments.models import InvestmentAccount
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchStatus, BatchType, TransactionStatus, TransactionType
from apps.ledger.models import Transaction, TransactionBatch
from apps.ledger.selectors import ZERO, net_by, with_balance
from apps.loans.models import Loan
from apps.members.models import Member, MembershipStatusChange, MemberStatus
from apps.notifications import services as notifications
from apps.savings.models import ProductKind, SavingsAccount

from .models import AccountClosureRequest

STATUS = AccountClosureRequest.Status


@transaction.atomic
def submit_request(member, *, reason_category, reason, confirmed, additional_information="", attachment=None):
    if member.status == MemberStatus.CLOSED:
        raise DomainError("This membership is already closed.", code="member_closed")
    if not confirmed:
        raise DomainError(
            "Please confirm that you understand what closing your account means.",
            code="confirmation_required",
            fields={"confirmed": ["Please confirm."]},
        )
    if AccountClosureRequest.objects.filter(member=member, status__in=AccountClosureRequest.OPEN_STATUSES).exists():
        raise DomainError("You already have a closure request in progress.", code="request_open")
    request = AccountClosureRequest.objects.create(
        member=member,
        reason_category=reason_category,
        reason=reason.strip(),
        additional_information=additional_information.strip(),
        confirmed=True,
        attachment=attachment or "",
    )
    record("closure.requested", actor=member.user, obj=request, metadata={"category": reason_category})
    return request


@transaction.atomic
def withdraw_request(member, closure_request):
    closure_request = AccountClosureRequest.objects.select_for_update().get(pk=closure_request.pk, member=member)
    if closure_request.status != STATUS.SUBMITTED:
        raise DomainError(
            "A request can only be withdrawn before an officer starts reviewing it.", code="invalid_transition"
        )
    closure_request.status = STATUS.WITHDRAWN
    closure_request.withdrawn_at = timezone.now()
    closure_request.save(update_fields=["status", "withdrawn_at", "updated_at"])
    record("closure.withdrawn", actor=member.user, obj=closure_request)
    return closure_request


# ---------------------------------------------------------------------------
# Officer side: review -> approve/reject -> execute (settlement batch) -> CLOSED
# ---------------------------------------------------------------------------

def _locked(closure_request):
    return AccountClosureRequest.objects.select_for_update(of=("self",)).select_related("member__user").get(pk=closure_request.pk)


def _notify(closure_request, title, body):
    notifications.notify_member(closure_request.member, category=notifications.Category.CLOSURE, title=title, body=body,
                                link=notifications.link("closure"))


def _assert_status(closure_request, allowed, action):
    if closure_request.status not in allowed:
        raise DomainError(
            f"A {closure_request.get_status_display().lower()} request cannot be {action}.", code="invalid_transition"
        )


def settlement_statement(member):
    """What closing this membership would settle, from current posted balances."""
    savings = [
        {"id": str(a.pk), "account_number": a.account_number, "label": str(a.cycle) if a.cycle_id else a.product.name,
         "kind": a.product.kind, "balance": a.balance}
        for a in with_balance(
            SavingsAccount.objects.filter(member=member).exclude(status=SavingsAccount.Status.CLOSED).select_related("product", "cycle"),
            "savings_account",
        )
    ]
    investments = [
        {"id": str(a.pk), "account_number": a.account_number, "label": a.product.name, "balance": a.balance}
        for a in with_balance(
            InvestmentAccount.objects.filter(member=member, status=InvestmentAccount.Status.ACTIVE).select_related("product"),
            "investment_account",
        )
    ]
    nets = net_by("loan", member=member)
    loans = [
        {"id": str(loan.pk), "reference": loan.reference, "outstanding": -nets.get(loan.pk, ZERO)}
        for loan in Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES)
    ]
    dividends = [
        {"financial_year": d.cycle.financial_year, "net_amount": d.net_amount}
        for d in MemberDividend.objects.filter(member=member, status=MemberDividend.Status.APPROVED).select_related("cycle")
    ]
    savings_total = sum((s["balance"] for s in savings), ZERO)
    investment_total = sum((i["balance"] for i in investments), ZERO)
    loan_total = sum((loan["outstanding"] for loan in loans), ZERO)
    net = savings_total + investment_total - loan_total
    return {
        "savings": savings,
        "investments": investments,
        "loans": loans,
        "unpaid_dividends": dividends,
        "savings_total": savings_total,
        "investment_total": investment_total,
        "loan_total": loan_total,
        "net_payable": net,
        "can_settle": net >= 0,
        "pending_entries": Transaction.objects.pending().filter(member=member).count(),
    }


@transaction.atomic
def start_review(actor, closure_request, *, notes=""):
    require_perm(actor, P.REVIEW_CLOSURE_REQUEST)
    closure_request = _locked(closure_request)
    assert_not_self(actor, closure_request.member, "review the closure of")
    _assert_status(closure_request, [STATUS.SUBMITTED], "put under review")
    closure_request.status = STATUS.UNDER_REVIEW
    closure_request.reviewed_by = actor
    closure_request.reviewed_at = timezone.now()
    closure_request.review_notes = notes
    closure_request.save()
    record("closure.review_started", actor=actor, obj=closure_request)
    _notify(closure_request, f"Closure request {closure_request.reference} is under review",
            "An officer is reviewing your request to close your account.")
    return closure_request


@transaction.atomic
def approve_request(actor, closure_request, *, notes=""):
    """Approval freezes the settlement statement; nothing moves until execution."""
    require_perm(actor, P.APPROVE_CLOSURE_REQUEST)
    closure_request = _locked(closure_request)
    assert_not_self(actor, closure_request.member, "approve the closure of")
    _assert_status(closure_request, [STATUS.UNDER_REVIEW], "approved (it must be reviewed first)")
    closure_request.status = STATUS.APPROVED
    closure_request.decided_by = actor
    closure_request.decided_at = timezone.now()
    closure_request.decision_reason = notes
    closure_request.settlement_statement = money_to_str(settlement_statement(closure_request.member))
    closure_request.save()
    record("closure.approved", actor=actor, obj=closure_request,
           metadata={"net_payable": closure_request.settlement_statement["net_payable"]})
    _notify(closure_request, f"Closure request {closure_request.reference} approved",
            "Your request was approved. Your accounts will be settled and closed shortly.")
    return closure_request


@transaction.atomic
def reject_request(actor, closure_request, *, reason):
    require_perm(actor, P.APPROVE_CLOSURE_REQUEST)
    closure_request = _locked(closure_request)
    assert_not_self(actor, closure_request.member, "decide the closure of")
    _assert_status(closure_request, [STATUS.SUBMITTED, STATUS.UNDER_REVIEW], "rejected")
    if not (reason or "").strip():
        raise DomainError("Give the member a reason.", code="reason_required", fields={"reason": ["Give the member a reason."]})
    closure_request.status = STATUS.REJECTED
    closure_request.decided_by = actor
    closure_request.decided_at = timezone.now()
    closure_request.decision_reason = reason.strip()
    closure_request.save()
    record("closure.rejected", actor=actor, obj=closure_request, metadata={"reason": reason.strip()})
    _notify(closure_request, f"Closure request {closure_request.reference} not approved", f"Reason: {reason.strip()}")
    return closure_request


def open_settlement_batch(closure_request):
    return TransactionBatch.objects.filter(
        batch_type=BatchType.CLOSURE_SETTLEMENT,
        status__in=[BatchStatus.VALIDATED, BatchStatus.SUBMITTED],
        validation_report__closure_request_id=str(closure_request.pk),
    ).first()


@transaction.atomic
def execute(actor, closure_request, *, value_date=None):
    """
    Settle and close. Loans are offset from savings (then investments) and the
    rest is paid out, all as one CLOSURE_SETTLEMENT batch that a second officer
    approves; posting it closes the membership. A member with nothing to settle
    is closed at once. Execution is refused while savings and investments
    cannot cover the loans (BR-24).
    """
    require_perm(actor, P.EXECUTE_ACCOUNT_CLOSURE)
    closure_request = _locked(closure_request)
    member = closure_request.member
    assert_not_self(actor, member, "close the account of")
    _assert_status(closure_request, [STATUS.APPROVED], "executed")
    if open_settlement_batch(closure_request):
        raise DomainError("A settlement batch for this closure is already awaiting approval.", code="settlement_in_progress")
    statement = settlement_statement(member)
    if statement["pending_entries"]:
        raise DomainError("This member has entries awaiting approval. Approve or reject them first.", code="pending_entries")
    if not statement["can_settle"]:
        shortfall = -statement["net_payable"]
        raise DomainError(
            f"Savings and investments do not cover the outstanding loans. The member must first repay ₦{shortfall:,.2f}.",
            code="loans_not_covered",
        )

    funds = [(SavingsAccount.objects.get(pk=s["id"]), s["balance"]) for s in statement["savings"] if s["balance"] > 0]
    funds += [(InvestmentAccount.objects.get(pk=i["id"]), i["balance"]) for i in statement["investments"] if i["balance"] > 0]
    loans = [(Loan.objects.get(pk=item["id"]), item["outstanding"]) for item in statement["loans"] if item["outstanding"] > 0]
    if not funds and not loans:
        return finalise(actor, closure_request), None

    def debit(batch, account, amount, description):
        # Closure settlement is an approved officer action, so it pays out
        # regardless of the products' everyday withdrawal settings.
        if isinstance(account, InvestmentAccount):
            txn_type = TransactionType.INVESTMENT_LIQUIDATION
        elif account.product.kind == ProductKind.CYCLE:
            txn_type = TransactionType.SAVINGS_CYCLE_PAYOUT
        else:
            txn_type = TransactionType.SAVINGS_WITHDRAWAL
        ledger.create_entry(actor, member=member, txn_type=txn_type, amount=amount, account=account, value_date=value_date,
                            description=description, batch=batch, closure_request=closure_request, audit=False)

    def build(batch):
        batch.validation_report = {"closure_request_id": str(closure_request.pk)}
        remaining = [[account, balance] for account, balance in funds]
        for loan, owed in loans:
            still_owed = owed
            for fund in remaining:
                if still_owed <= 0:
                    break
                take = min(fund[1], still_owed)
                if take > 0:
                    debit(batch, fund[0], take, f"Applied to loan {loan.reference} at account closure")
                    fund[1] -= take
                    still_owed -= take
            ledger.create_entry(actor, member=member, txn_type=TransactionType.LOAN_REPAYMENT, amount=owed, account=loan,
                                value_date=value_date, description=f"Settled from savings at account closure ({closure_request.reference})",
                                batch=batch, closure_request=closure_request, audit=False)
        for account, balance in remaining:
            if balance > 0:
                debit(batch, account, balance, f"Paid out at account closure ({closure_request.reference})")

    batch = ledger.create_batch_from_entries(
        actor, batch_type=BatchType.CLOSURE_SETTLEMENT, build_lines=build, description=f"Closure settlement {closure_request.reference}"
    )
    record("closure.settlement_prepared", actor=actor, obj=closure_request, metadata={"batch": batch.reference})
    return closure_request, batch


def finalise(actor, closure_request):
    """Close every account and the membership. Records are kept (BR-13)."""
    closure_request = _locked(closure_request)
    member = Member.objects.select_for_update(of=("self",)).select_related("user").get(pk=closure_request.member_id)
    today, now = timezone.localdate(), timezone.now()
    SavingsAccount.objects.filter(member=member).exclude(status=SavingsAccount.Status.CLOSED).update(
        status=SavingsAccount.Status.CLOSED, closed_on=today, updated_at=now
    )
    InvestmentAccount.objects.filter(member=member, status=InvestmentAccount.Status.ACTIVE).update(
        status=InvestmentAccount.Status.CLOSED, closed_on=today, updated_at=now
    )
    previous = member.status
    member.status = MemberStatus.CLOSED
    member.closed_at = now
    member.status_reason = f"Closed on request {closure_request.reference}"
    member.save(update_fields=["status", "closed_at", "status_reason", "updated_at"])
    MembershipStatusChange.objects.create(member=member, from_status=previous, to_status=MemberStatus.CLOSED,
                                          reason=closure_request.get_reason_category_display(), changed_by=actor,
                                          closure_request=closure_request)
    if CooperativeSettings.load().closure_disables_portal_login:
        member.user.is_active = False
        member.user.save(update_fields=["is_active", "updated_at"])
        revoke_refresh_tokens(member.user)
    closure_request.status = STATUS.CLOSED
    closure_request.closed_by = actor
    closure_request.closed_at = now
    closure_request.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    record("closure.executed", actor=actor, obj=closure_request, metadata={"member": member.membership_number})
    _notify(closure_request, "Your membership has been closed",
            "Your accounts have been settled and closed. Thank you for being a member of the cooperative.")
    return closure_request


class ClosureSettlementBatchHandler(BatchHandler):
    """Built by execute(); posting it closes the membership."""

    batch_type = BatchType.CLOSURE_SETTLEMENT
    permissions = (P.EXECUTE_ACCOUNT_CLOSURE,)
    accepts_files = False

    def revalidate(self, batch):
        problems = []
        debits, credits = {}, {}
        entries = batch.transactions.filter(status=TransactionStatus.PENDING).select_related(
            "savings_account", "investment_account", "loan", "member"
        )
        for entry in entries:
            account = entry.savings_account or entry.investment_account or entry.loan
            bucket = credits if entry.loan_id else debits
            bucket.setdefault(account, [ZERO, entry])
            bucket[account][0] += entry.amount
        for account, (total, entry) in debits.items():
            if total > ledger.posted_balance(account):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"{account} no longer holds ₦{total:,.2f}."]})
        for loan, (total, entry) in credits.items():
            if total > -ledger.posted_balance(loan):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"{loan.reference} now owes less than ₦{total:,.2f}."]})
        return problems

    def after_post(self, batch):
        closure_request = AccountClosureRequest.objects.get(pk=batch.validation_report["closure_request_id"])
        finalise(batch.approved_by, closure_request)
