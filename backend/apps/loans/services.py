"""
Loans (ARCHITECTURE.md §6.2).

Application: DRAFT -> SUBMITTED -> UNDER_REVIEW -> APPROVED -> DISBURSED
             (RETURNED for more information, REJECTED, CANCELLED)
Loan:        PENDING_DISBURSEMENT -> ACTIVE -> COMPLETED   (DEFAULTED; CANCELLED if the
             disbursement is rejected, after which it can be disbursed again)

The loan only becomes ACTIVE, and interest is only charged, when the
disbursement entry actually posts (at once, or after second-officer approval).
Repayments are allocated to instalments when they post: oldest instalment
first, interest before principal.
"""
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.money import to_money
from apps.common.serializers import money_to_str
from apps.ledger import services as ledger
from apps.ledger.choices import EntrySide, TransactionStatus, TransactionType
from apps.ledger.hooks import on_posted, on_rejected, on_reversed
from apps.ledger.models import Transaction
from apps.members.models import Member, MemberStatus
from apps.notifications import services as notifications

from .calculators import schedule_for_product
from .eligibility import evaluate, hard_failures
from .selectors import guarantee_room, guarantor_problem
from .models import (
    InterestCollection,
    InterestMethod,
    InterestRateBasis,
    Loan,
    LoanApplication,
    LoanGuarantor,
    LoanProduct,
    LoanRepayment,
    RepaymentAllocation,
    RepaymentInstallment,
)

APP = LoanApplication.Status
UPFRONT_INTEREST_REFERENCE = "UPFRONT-INTEREST"

PRODUCT_FIELDS = [
    "name",
    "code",
    "description",
    "interest_rate",
    "interest_rate_basis",
    "interest_method",
    "interest_collection",
    "min_amount",
    "max_amount",
    "max_savings_multiple",
    "min_term_months",
    "max_term_months",
    "allowed_terms",
    "min_membership_months",
    "max_active_loans",
    "guarantors_required",
    "required_documents",
    "allow_topup",
    "is_active",
]


def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


def _money_str(value):
    return f"₦{value:,.2f}"


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def _validate_product(data):
    if data["min_amount"] > data["max_amount"]:
        _field_error("max_amount", "The maximum must be at least the minimum.", "invalid_amount_range")
    if data["min_term_months"] > data["max_term_months"]:
        _field_error("max_term_months", "The maximum term must be at least the minimum.", "invalid_term_range")
    bad_terms = [t for t in data.get("allowed_terms") or [] if not data["min_term_months"] <= t <= data["max_term_months"]]
    if bad_terms:
        _field_error("allowed_terms", f"Terms {bad_terms} are outside the term range.", "invalid_terms")
    if data["interest_method"] == InterestMethod.REDUCING_BALANCE and data["interest_rate_basis"] == InterestRateBasis.PER_LOAN:
        _field_error("interest_rate_basis", "Reducing-balance loans need a per-annum or per-month rate.", "invalid_rate_basis")
    if data.get("guarantors_required", 1) < 1:
        _field_error("guarantors_required", "Every loan needs at least one guarantor.", "guarantor_required")


def _assert_unique_product(name, code, exclude_pk=None):
    qs = LoanProduct.objects.exclude(pk=exclude_pk) if exclude_pk else LoanProduct.objects.all()
    if qs.filter(name__iexact=name).exists():
        _field_error("name", "A loan product with this name already exists.", "duplicate_name")
    if qs.filter(code__iexact=code).exists():
        _field_error("code", "A loan product with this code already exists.", "duplicate_code")


@transaction.atomic
def create_product(actor, **data):
    require_perm(actor, P.MANAGE_LOAN_PRODUCTS)
    defaults = {f.name: f.get_default() for f in LoanProduct._meta.fields if f.name in PRODUCT_FIELDS}
    merged = {**defaults, **data}
    _validate_product(merged)
    _assert_unique_product(merged["name"], merged["code"])
    product = LoanProduct.objects.create(**data)
    record("loan.product_created", actor=actor, obj=product)
    return product


@transaction.atomic
def update_product(actor, product, **data):
    """Existing loans keep their snapshotted terms (D6); only future loans are affected."""
    require_perm(actor, P.MANAGE_LOAN_PRODUCTS)
    merged = {f: data.get(f, getattr(product, f)) for f in PRODUCT_FIELDS}
    _validate_product(merged)
    _assert_unique_product(merged["name"], merged["code"], exclude_pk=product.pk)
    changes = {}
    for field in PRODUCT_FIELDS:
        if field in data and getattr(product, field) != data[field]:
            changes[field] = [getattr(product, field), data[field]]
            setattr(product, field, data[field])
    if changes:
        product.save()
        record("loan.product_updated", actor=actor, obj=product, changes=changes)
    return product


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def _lock(application):
    return LoanApplication.objects.select_for_update(of=("self",)).select_related("member", "product").get(pk=application.pk)


def _acting_for_member(actor, application):
    """
    Members act on their own applications. Officers may act on a member's
    behalf (paper applications) with review permission, never for themselves.
    """
    if application.member.user_id == actor.pk:
        return
    require_perm(actor, P.REVIEW_LOAN_APPLICATION)
    assert_not_self(actor, application.member, "file loan applications for")


def _assert_status(application, allowed, action):
    if application.status not in allowed:
        raise DomainError(
            f"A {application.get_status_display().lower()} application cannot be {action}.", code="invalid_transition"
        )


@transaction.atomic
def create_application(actor, *, member, product, amount_requested, term_months, purpose):
    if member.user_id != actor.pk:
        require_perm(actor, P.REVIEW_LOAN_APPLICATION)
        assert_not_self(actor, member, "file loan applications for")
    if not product.is_active:
        _field_error("product", f"{product.name} is not open to new applications.", "inactive_product")
    application = LoanApplication.objects.create(
        member=member,
        product=product,
        amount_requested=to_money(amount_requested),
        term_months=term_months,
        purpose=purpose,
    )
    record("loan.application_created", actor=actor, obj=application, metadata={"on_behalf": member.user_id != actor.pk})
    return application


@transaction.atomic
def update_application(actor, application, **data):
    application = _lock(application)
    _acting_for_member(actor, application)
    _assert_status(application, [APP.DRAFT, APP.RETURNED], "edited")
    if "product" in data and data["product"] != application.product and application.status != APP.DRAFT:
        _field_error("product", "The product can only change while the application is a draft.", "product_locked")
    changes = {}
    for field in ("product", "amount_requested", "term_months", "purpose"):
        if field in data and getattr(application, field) != data[field]:
            changes[field] = [str(getattr(application, field)), str(data[field])]
            setattr(application, field, data[field])
    if changes:
        application.save()
        record("loan.application_updated", actor=actor, obj=application, changes=changes)
    return application


@transaction.atomic
def submit_application(actor, application):
    application = _lock(application)
    _acting_for_member(actor, application)
    _assert_status(application, [APP.DRAFT, APP.RETURNED], "submitted")
    result = evaluate(
        application.member,
        application.product,
        amount=application.amount_requested,
        term_months=application.term_months,
        exclude_application=application,
    )
    failures = hard_failures(result)
    if failures:
        raise DomainError(
            "This application does not meet the loan requirements: " + "; ".join(c["label"] for c in failures) + ".",
            code="not_eligible",
            fields={"checks": failures},
        )
    needed = application.product.guarantors_required
    standing = application.guarantors.exclude(status=LoanGuarantor.Status.DECLINED).count()
    if standing < needed:
        message = (f"This loan needs {needed} guarantor(s); add {needed - standing} more using their membership number."
                   if standing else f"This loan needs {needed} guarantor(s). Add a guarantor using their membership number.")
        _field_error("guarantors", message, "guarantors_required")
    _assert_shares_fit(application)
    previous = application.status
    application.status = APP.SUBMITTED
    application.submitted_at = timezone.now()
    application.eligibility_snapshot = {**money_to_str(result), "evaluated_at": timezone.now().isoformat()}
    application.save()
    record("loan.application_submitted", actor=actor, obj=application, changes={"status": [previous, APP.SUBMITTED]})
    _request_guarantees(application)
    return application


# ---------------------------------------------------------------------------
# Guarantors (BR-28)
# ---------------------------------------------------------------------------

MAX_GUARANTORS = 5
G = LoanGuarantor.Status


def find_guarantor(applicant, membership_number):
    """The member who may stand as guarantor for `applicant`, found by membership number."""
    number = (membership_number or "").strip()
    if not number:
        _field_error("membership_number", "Enter the guarantor's membership number.", "required")
    member = Member.objects.select_related("user").filter(membership_number__iexact=number).first()
    if member is None:
        _field_error("membership_number", f"No member has the membership number {number}.", "guarantor_not_found")
    if member.pk == applicant.pk:
        _field_error("membership_number", "You cannot be your own guarantor.", "guarantor_is_applicant")
    if guarantor_problem(member):
        _field_error("membership_number", "This member cannot stand as a guarantor at the moment.", "guarantor_not_active")
    room = guarantee_room(member)
    if room is not None and room <= 0:
        _field_error("membership_number", "This member cannot stand as a guarantor at the moment.", "guarantee_limit")
    return member


@transaction.atomic
def add_guarantor(actor, application, membership_number):
    application = _lock(application)
    _acting_for_member(actor, application)
    _assert_status(application, [APP.DRAFT, APP.RETURNED], "changed")
    member = find_guarantor(application.member, membership_number)
    if application.guarantors.filter(guarantor=member).exists():
        _field_error("membership_number", f"{member.full_name} is already a guarantor on this application.", "duplicate_guarantor")
    if application.guarantors.exclude(status=G.DECLINED).count() >= MAX_GUARANTORS:
        _field_error("membership_number", f"An application can have at most {MAX_GUARANTORS} guarantors.", "too_many_guarantors")
    guarantee = LoanGuarantor.objects.create(application=application, guarantor=member, amount_guaranteed=application.amount_requested)
    record("loan.guarantor_added", actor=actor, obj=application,
           metadata={"guarantor": member.membership_number, "guarantee_id": str(guarantee.pk)})
    return guarantee


@transaction.atomic
def remove_guarantor(actor, application, guarantee):
    application = _lock(application)
    _acting_for_member(actor, application)
    _assert_status(application, [APP.DRAFT, APP.RETURNED], "changed")
    if guarantee.application_id != application.pk:
        raise DomainError("That guarantor is not on this application.", code="not_found")
    record("loan.guarantor_removed", actor=actor, obj=application,
           metadata={"guarantor": guarantee.guarantor.membership_number, "status": guarantee.status})
    guarantee.delete()


def _assert_shares_fit(application):
    """BR-31: each guarantor's share must fit within what they may still guarantee."""
    guarantees = list(application.guarantors.exclude(status=G.DECLINED).select_related("guarantor").order_by("created_at"))
    for guarantee, share in zip(guarantees, _shares(application.amount_requested, len(guarantees))):
        room = guarantee_room(guarantee.guarantor, exclude=guarantee)
        if room is not None and share > room:
            _field_error(
                "guarantors",
                f"{guarantee.guarantor.full_name} cannot guarantee {_money_str(share)}. "
                "Add another guarantor to share the amount, or choose a different guarantor.",
                "guarantee_limit",
            )


def _shares(amount, count):
    """Split the amount requested equally; the first guarantor carries any kobo left over."""
    base = (amount / count).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return [amount - base * (count - 1)] + [base] * (count - 1)


def _request_guarantees(application):
    """
    On submission: share the amount among the guarantors, and ask (notify and
    e-mail) everyone who hasn't been asked for this amount yet. If the amount
    changed since a guarantor accepted, their acceptance no longer applies and
    they are asked again.
    """
    guarantees = list(application.guarantors.exclude(status=G.DECLINED).select_related("guarantor__user").order_by("created_at"))
    applicant = application.member
    now = timezone.now()
    for guarantee, share in zip(guarantees, _shares(application.amount_requested, len(guarantees))):
        changed = guarantee.amount_guaranteed != share
        if changed and guarantee.status == G.ACCEPTED:
            guarantee.status, guarantee.responded_at = G.PENDING, None
        if guarantee.status == G.PENDING and (guarantee.requested_at is None or changed):
            guarantee.requested_at = now
            notifications.notify_member(
                guarantee.guarantor, category=notifications.Category.LOAN, email=True,
                title=f"Guarantor request from {applicant.full_name}",
                body=(f"{applicant.full_name} ({applicant.membership_number}) has asked you to stand as guarantor for a "
                      f"{application.product.name} of {_money_str(application.amount_requested)} over {application.term_months} months "
                      f"(application {application.reference}). Your share of the guarantee is {_money_str(share)}. "
                      "Please accept or decline in the member portal under Guarantees."),
                link=notifications.link("guarantees"),
            )
        guarantee.amount_guaranteed = share
        guarantee.save()


@transaction.atomic
def respond_to_guarantee(actor, guarantee, *, accept, reason=""):
    """The guarantor accepts or declines. Declining sends the application back to the applicant."""
    guarantee = LoanGuarantor.objects.select_for_update().select_related("guarantor", "application").get(pk=guarantee.pk)
    if guarantee.guarantor.user_id != actor.pk:
        raise PermissionDenied("Only the guarantor can respond to this request.")
    application = _lock(guarantee.application)
    if guarantee.status != G.PENDING or guarantee.requested_at is None:
        raise DomainError("This request has already been answered.", code="already_answered")
    if application.status not in (APP.SUBMITTED, APP.UNDER_REVIEW):
        raise DomainError("This application is no longer waiting for guarantors.", code="not_awaiting_guarantors")
    guarantor, applicant = guarantee.guarantor, application.member
    if accept and guarantor_problem(guarantor):
        raise DomainError("You cannot accept while your membership is inactive or being closed.", code="guarantor_not_active")
    if accept:
        room = guarantee_room(guarantor, exclude=guarantee)
        if room is not None and guarantee.amount_guaranteed > room:
            raise DomainError(
                f"Accepting would take your guarantees above your limit. You can guarantee up to "
                f"{_money_str(max(room, Decimal('0')))} more (your limit is a multiple of your savings).",
                code="guarantee_limit",
            )
    guarantee.responded_at = timezone.now()
    if accept:
        guarantee.status = G.ACCEPTED
        guarantee.save()
        record("loan.guarantee_accepted", actor=actor, obj=application, metadata={"guarantor": guarantor.membership_number})
        accepted = application.guarantors.filter(status=G.ACCEPTED).count()
        complete = accepted >= application.product.guarantors_required
        notifications.notify_member(
            applicant, category=notifications.Category.LOAN, email=True,
            title=f"{guarantor.full_name} accepted to guarantee your loan",
            body=(f"{guarantor.full_name} has agreed to guarantee {_money_str(guarantee.amount_guaranteed)} of your application "
                  f"{application.reference}. "
                  + ("All your guarantors have accepted, so the loan committee can now decide." if complete
                     else "We are still waiting for your other guarantor(s).")),
            link=notifications.link("application", id=application.pk),
        )
        return guarantee

    reason = (reason or "").strip()
    guarantee.status = G.DECLINED
    guarantee.decline_reason = reason
    guarantee.save()
    previous = application.status
    application.status = APP.RETURNED
    application.info_request_message = (
        f"{guarantor.full_name} declined to stand as your guarantor" + (f" ({reason})" if reason else "")
        + ". Please choose another guarantor and resubmit."
    )
    application.save()
    record("loan.guarantee_declined", actor=actor, obj=application,
           changes={"status": [previous, APP.RETURNED]}, metadata={"guarantor": guarantor.membership_number, "reason": reason})
    notifications.notify_member(
        applicant, category=notifications.Category.LOAN, email=True,
        title=f"{guarantor.full_name} declined to guarantee your loan",
        body=application.info_request_message,
        link=notifications.link("application", id=application.pk),
    )
    return guarantee


@transaction.atomic
def cancel_application(actor, application, *, reason=""):
    application = _lock(application)
    if application.member.user_id != actor.pk:
        raise PermissionDenied("Only the applicant can cancel an application.")
    _assert_status(application, [APP.DRAFT, APP.SUBMITTED, APP.UNDER_REVIEW, APP.RETURNED, APP.APPROVED], "cancelled")
    if application.loans.filter(status=Loan.Status.PENDING_DISBURSEMENT).exists():
        raise DomainError("The loan is already being disbursed.", code="disbursement_pending")
    previous = application.status
    application.status = APP.CANCELLED
    application.cancelled_at = timezone.now()
    application.save()
    record("loan.application_cancelled", actor=actor, obj=application, changes={"status": [previous, APP.CANCELLED]}, metadata={"reason": reason})
    return application


@transaction.atomic
def start_review(actor, application, *, notes=""):
    require_perm(actor, P.REVIEW_LOAN_APPLICATION)
    application = _lock(application)
    assert_not_self(actor, application.member, "review loans for")
    _assert_status(application, [APP.SUBMITTED], "put under review")
    application.status = APP.UNDER_REVIEW
    application.reviewed_by = actor
    application.reviewed_at = timezone.now()
    if notes:
        application.review_notes = notes
    application.save()
    record("loan.application_review_started", actor=actor, obj=application)
    return application


@transaction.atomic
def return_application(actor, application, *, message):
    require_perm(actor, P.REVIEW_LOAN_APPLICATION)
    application = _lock(application)
    assert_not_self(actor, application.member, "review loans for")
    _assert_status(application, [APP.SUBMITTED, APP.UNDER_REVIEW], "returned")
    if not (message or "").strip():
        _field_error("message", "Tell the member what is needed.", "message_required")
    application.status = APP.RETURNED
    application.info_request_message = message.strip()
    application.reviewed_by = actor
    application.reviewed_at = timezone.now()
    application.save()
    record("loan.application_returned", actor=actor, obj=application, metadata={"message": message.strip()})
    notifications.notify_member(
        application.member, category=notifications.Category.LOAN,
        title=f"Loan application {application.reference} needs changes",
        body=f"An officer returned your application with this note: {message.strip()} Please update it and submit it again.",
        link=notifications.link("application", id=application.pk),
    )
    return application


@transaction.atomic
def approve_application(actor, application, *, approved_amount=None, approved_term_months=None, notes=""):
    require_perm(actor, P.APPROVE_LOAN_APPLICATION)
    application = _lock(application)
    assert_not_self(actor, application.member, "approve loans for")
    _assert_status(application, [APP.UNDER_REVIEW], "approved (it must be reviewed first)")
    amount = to_money(approved_amount) if approved_amount is not None else application.amount_requested
    term = approved_term_months or application.term_months

    result = evaluate(application.member, application.product, amount=amount, term_months=term, exclude_application=application)
    failures = hard_failures(result)
    if failures:
        raise DomainError(
            "The loan cannot be approved on these terms: " + "; ".join(c["label"] for c in failures) + ".",
            code="not_eligible",
            fields={"checks": failures},
        )
    needed = application.product.guarantors_required
    accepted = application.guarantors.filter(status=LoanGuarantor.Status.ACCEPTED).select_related("guarantor")
    lapsed = [g.guarantor for g in accepted if guarantor_problem(g.guarantor)]
    if len(accepted) - len(lapsed) < needed:
        detail = f" {', '.join(m.full_name for m in lapsed)} can no longer stand as guarantor." if lapsed else ""
        raise DomainError(
            f"{needed} accepted guarantor(s) in good standing are required; {len(accepted) - len(lapsed)} so far.{detail}",
            code="guarantors_required",
        )

    application.status = APP.APPROVED
    application.approved_amount = amount
    application.approved_term_months = term
    application.decided_by = actor
    application.decided_at = timezone.now()
    application.decision_reason = notes
    application.save()
    record(
        "loan.application_approved",
        actor=actor,
        obj=application,
        metadata={"requested": application.amount_requested, "approved": amount, "term_months": term},
    )
    notifications.notify_member(
        application.member, category=notifications.Category.LOAN,
        title=f"Loan application {application.reference} approved",
        body=f"Your {application.product.name} application was approved for {notifications.naira(amount)} over {term} months. "
             "You will be notified when it is paid out.",
        link=notifications.link("application", id=application.pk),
    )
    return application


@transaction.atomic
def reject_application(actor, application, *, reason):
    require_perm(actor, P.APPROVE_LOAN_APPLICATION)
    application = _lock(application)
    assert_not_self(actor, application.member, "decide loans for")
    _assert_status(application, [APP.SUBMITTED, APP.UNDER_REVIEW], "rejected")
    if not (reason or "").strip():
        _field_error("reason", "Give the member a reason.", "reason_required")
    application.status = APP.REJECTED
    application.decided_by = actor
    application.decided_at = timezone.now()
    application.decision_reason = reason.strip()
    application.save()
    record("loan.application_rejected", actor=actor, obj=application, metadata={"reason": reason.strip()})
    notifications.notify_member(
        application.member, category=notifications.Category.LOAN,
        title=f"Loan application {application.reference} not approved",
        body=f"Reason: {reason.strip()}",
        link=notifications.link("application", id=application.pk),
    )
    return application


# ---------------------------------------------------------------------------
# Disbursement
# ---------------------------------------------------------------------------

@transaction.atomic
def disburse(actor, application, *, disbursed_on=None, external_reference=""):
    """
    Create the loan (terms snapshotted, schedule generated) and its
    disbursement entry. With maker-checker (the default) the loan waits in
    PENDING_DISBURSEMENT until another officer approves the entry.
    """
    require_perm(actor, P.DISBURSE_LOAN)
    application = _lock(application)
    assert_not_self(actor, application.member, "disburse loans to")
    _assert_status(application, [APP.APPROVED], "disbursed")
    if application.loans.filter(status=Loan.Status.PENDING_DISBURSEMENT).exists():
        raise DomainError("A disbursement for this application is already awaiting approval.", code="disbursement_pending")
    disbursed_on = disbursed_on or timezone.localdate()
    if disbursed_on > timezone.localdate():
        _field_error("disbursed_on", "Cannot be in the future.", "future_date")

    product = application.product
    schedule = schedule_for_product(product, application.approved_amount, application.approved_term_months, disbursed_on)
    loan = Loan.objects.create(
        application=application,
        member=application.member,
        product=product,
        principal=application.approved_amount,
        interest_rate=product.interest_rate,
        interest_rate_basis=product.interest_rate_basis,
        interest_method=product.interest_method,
        interest_collection=product.interest_collection,
        term_months=application.approved_term_months,
        total_interest=schedule.total_interest,
        disbursed_on=disbursed_on,
        first_due_date=schedule.first_due_date,
        maturity_date=schedule.maturity_date,
        status=Loan.Status.PENDING_DISBURSEMENT,
    )
    RepaymentInstallment.objects.bulk_create(
        [
            RepaymentInstallment(loan=loan, number=i.number, due_date=i.due_date, principal_due=i.principal, interest_due=i.interest)
            for i in schedule.instalments
        ]
    )
    record("loan.disbursement_requested", actor=actor, obj=loan, metadata={"application": application.reference, "principal": loan.principal})
    ledger.create_entry(
        actor,
        member=loan.member,
        txn_type=TransactionType.LOAN_DISBURSEMENT,
        amount=loan.principal,
        account=loan,
        value_date=disbursed_on,
        description=f"Disbursement of {loan.reference} ({product.name})",
        external_reference=external_reference,
    )
    loan.refresh_from_db()
    return loan


@on_posted(TransactionType.LOAN_DISBURSEMENT)
def _activate_loan(entry):
    loan = Loan.objects.select_for_update().get(pk=entry.loan_id)
    if loan.status != Loan.Status.PENDING_DISBURSEMENT:
        return
    actor = entry.approved_by or entry.created_by
    if loan.total_interest > 0:
        ledger.create_entry(
            actor,
            member=loan.member,
            txn_type=TransactionType.LOAN_INTEREST_CHARGE,
            amount=loan.total_interest,
            account=loan,
            value_date=entry.value_date,
            description=f"Interest on {loan.reference}",
            require_approval=False,
            audit=False,
        )
        if loan.interest_collection == InterestCollection.UPFRONT:
            ledger.create_entry(
                actor,
                member=loan.member,
                txn_type=TransactionType.LOAN_REPAYMENT,
                amount=loan.total_interest,
                account=loan,
                value_date=entry.value_date,
                description="Interest deducted at disbursement",
                external_reference=UPFRONT_INTEREST_REFERENCE,
                require_approval=False,
                audit=False,
            )
    loan.status = Loan.Status.ACTIVE
    loan.save(update_fields=["status", "updated_at"])
    if loan.application_id:
        LoanApplication.objects.filter(pk=loan.application_id).update(status=APP.DISBURSED, updated_at=timezone.now())
    record("loan.disbursed", actor=actor, obj=loan, metadata={"principal": loan.principal, "interest": loan.total_interest})
    notifications.notify_member(
        loan.member, category=notifications.Category.LOAN,
        title=f"Loan {loan.reference} disbursed",
        body=f"{notifications.naira(loan.principal)} has been paid out. Your first repayment is due {loan.first_due_date:%d %b %Y}.",
        link=notifications.link("loan", id=loan.pk),
    )


@on_rejected(TransactionType.LOAN_DISBURSEMENT)
def _cancel_loan(entry):
    loan = Loan.objects.select_for_update().get(pk=entry.loan_id)
    if loan.status == Loan.Status.PENDING_DISBURSEMENT:
        loan.status = Loan.Status.CANCELLED
        loan.save(update_fields=["status", "updated_at"])
        record("loan.disbursement_rejected", actor=entry.approved_by or entry.created_by, obj=loan)


# ---------------------------------------------------------------------------
# Repayments
# ---------------------------------------------------------------------------

def outstanding(loan):
    """Debits (disbursement, interest) minus credits (repayments) on posted entries."""
    return -ledger.posted_balance(loan)


def pending_repayments(loan, *, exclude_batch=None):
    qs = Transaction.objects.pending().filter(loan=loan, entry_side=EntrySide.CREDIT)
    if exclude_batch is not None:
        qs = qs.exclude(batch=exclude_batch)
    return qs.aggregate(total=Sum("amount"))["total"] or 0


def repayable(loan, *, exclude_batch=None):
    """How much more can be repaid now, allowing for repayments already awaiting approval."""
    return outstanding(loan) - pending_repayments(loan, exclude_batch=exclude_batch)


def assert_repayable(loan, amount):
    if loan.status not in Loan.RUNNING_STATUSES:
        raise DomainError(f"This loan is {loan.get_status_display().lower()}.", code="loan_not_running")
    available = repayable(loan)
    if amount > available:
        raise DomainError(
            f"The repayment is more than the {_money_str(available)} still owed.", code="overpayment",
            fields={"amount": [f"At most {_money_str(available)}."]},
        )


@transaction.atomic
def record_repayment(actor, loan, *, amount, value_date=None, period=None, description="", external_reference=""):
    require_perm(actor, P.RECORD_LOAN_REPAYMENT)
    loan = ledger.lock_account(loan)
    assert_not_self(actor, loan.member, "record repayments for")
    amount = to_money(amount)
    assert_repayable(loan, amount)
    value_date = value_date or timezone.localdate()
    return ledger.create_entry(
        actor,
        member=loan.member,
        txn_type=TransactionType.LOAN_REPAYMENT,
        amount=amount,
        account=loan,
        value_date=value_date,
        period=period or value_date.replace(day=1),
        description=description or f"Repayment of {loan.reference}",
        external_reference=external_reference,
    )


def paid_by_instalment(loan):
    """{instalment_id: (principal_paid, interest_paid)} from allocations of posted repayments."""
    rows = (
        RepaymentAllocation.objects.filter(installment__loan=loan, repayment__transaction__status=TransactionStatus.POSTED)
        .values("installment")
        .annotate(principal=Sum("principal_amount"), interest=Sum("interest_amount"))
    )
    return {r["installment"]: (r["principal"], r["interest"]) for r in rows}


@on_posted(TransactionType.LOAN_REPAYMENT)
def _allocate_repayment(entry):
    loan = Loan.objects.select_for_update().get(pk=entry.loan_id)
    if entry.external_reference == UPFRONT_INTEREST_REFERENCE:
        LoanRepayment.objects.create(transaction=entry, loan=loan, interest_component=entry.amount)
        return

    repayment = LoanRepayment.objects.create(transaction=entry, loan=loan)
    paid = paid_by_instalment(loan)
    remaining = entry.amount
    principal_total = interest_total = 0
    for instalment in loan.installments.order_by("number"):
        if remaining <= 0:
            break
        principal_paid, interest_paid = paid.get(instalment.pk, (0, 0))
        interest = min(remaining, instalment.interest_due - interest_paid)
        remaining -= interest
        principal = min(remaining, instalment.principal_due - principal_paid)
        remaining -= principal
        if interest or principal:
            RepaymentAllocation.objects.create(
                repayment=repayment, installment=instalment, principal_amount=principal, interest_amount=interest
            )
            principal_total += principal
            interest_total += interest
    if remaining > 0:
        raise DomainError("The repayment is more than the loan's remaining schedule.", code="overpayment")

    repayment.principal_component = principal_total
    repayment.interest_component = interest_total
    repayment.save(update_fields=["principal_component", "interest_component", "updated_at"])

    if outstanding(loan) <= 0:
        loan.status = Loan.Status.COMPLETED
        loan.completed_on = entry.value_date
        loan.save(update_fields=["status", "completed_on", "updated_at"])
        record("loan.completed", actor=entry.approved_by or entry.created_by, obj=loan)


@on_reversed(TransactionType.LOAN_REPAYMENT)
def _reopen_after_reversal(original):
    """A reversed repayment no longer counts: its allocations drop out and a completed loan reopens."""
    loan = Loan.objects.select_for_update().get(pk=original.loan_id)
    if loan.status == Loan.Status.COMPLETED and outstanding(loan) > 0:
        loan.status = Loan.Status.ACTIVE
        loan.completed_on = None
        loan.save(update_fields=["status", "completed_on", "updated_at"])
        record("loan.reopened", obj=loan, metadata={"reversed_repayment": original.reference})


# ---------------------------------------------------------------------------
# Default
# ---------------------------------------------------------------------------

@transaction.atomic
def mark_default(actor, loan, *, reason):
    from .selectors import loan_arrears

    require_perm(actor, P.MARK_LOAN_DEFAULT)
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    assert_not_self(actor, loan.member, "mark defaults for")
    if loan.status != Loan.Status.ACTIVE:
        raise DomainError(f"This loan is {loan.get_status_display().lower()}.", code="loan_not_running")
    if not (reason or "").strip():
        _field_error("reason", "Please give a reason.", "reason_required")
    if loan_arrears(loan)["amount"] <= 0:
        raise DomainError("This loan has no overdue instalments.", code="not_overdue")
    loan.status = Loan.Status.DEFAULTED
    loan.defaulted_on = timezone.localdate()
    loan.save(update_fields=["status", "defaulted_on", "updated_at"])
    record("loan.defaulted", actor=actor, obj=loan, metadata={"reason": reason.strip()})
    notifications.notify_member(
        loan.member, category=notifications.Category.LOAN,
        title=f"Loan {loan.reference} is in default",
        body="Repayments on this loan are overdue. Please contact the cooperative secretariat to arrange payment.",
        link=notifications.link("loan", id=loan.pk),
    )
    return loan
