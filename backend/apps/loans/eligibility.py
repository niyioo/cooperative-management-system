"""
Loan eligibility (BR-22). One function produces the list of checks shown to
the member before applying, stored as a snapshot at submission, and re-run
with the approved amount at approval. Hard failures block; soft ones warn.
"""
from decimal import Decimal

from django.utils import timezone

from apps.configuration.models import CooperativeSettings
from apps.ledger.selectors import ZERO, net_by
from apps.members.models import MemberStatus
from apps.savings.models import SavingsAccount
from apps.savings.rules import months_of_membership
from apps.savings.statutory import statutory_account

from .models import Loan, LoanApplication

OPEN_APPLICATION_STATUSES = [
    LoanApplication.Status.SUBMITTED,
    LoanApplication.Status.UNDER_REVIEW,
    LoanApplication.Status.RETURNED,
    LoanApplication.Status.APPROVED,
]


def eligible_savings(member):
    """
    The savings loans are measured against (BR-32): the member's Regular Savings,
    built from the statutory monthly contributions. Christmas Savings and other
    products don't count.
    """
    account = statutory_account(member)
    if account is None or account.status == SavingsAccount.Status.CLOSED:
        return ZERO
    return net_by("savings_account", savings_account=account).get(account.pk, ZERO)


def current_borrowing(member, exclude_application=None):
    """
    What the member already owes or has been granted: the balance still owed on
    running loans, loans approved and awaiting disbursement, and approved
    applications not yet disbursed.
    """
    owed = net_by("loan", member=member, loan__status__in=Loan.RUNNING_STATUSES)
    total = sum((-amount for amount in owed.values()), ZERO)
    total += sum(Loan.objects.filter(member=member, status=Loan.Status.PENDING_DISBURSEMENT).values_list("principal", flat=True), ZERO)
    approved = LoanApplication.objects.filter(member=member, status=LoanApplication.Status.APPROVED, loans__isnull=True)
    if exclude_application is not None:
        approved = approved.exclude(pk=exclude_application.pk)
    total += sum((a.approved_amount or a.amount_requested for a in approved), ZERO)
    return max(total, ZERO)


def borrowing_limit(member):
    """The most the member may owe in total (BR-32), or None when there is no cooperative limit."""
    multiple = CooperativeSettings.load().loan_savings_multiple
    if multiple is None:
        return None
    return (eligible_savings(member) * multiple).quantize(Decimal("0.01"))


def maximum_amount(product, member, exclude_application=None):
    """The most this member could borrow on this product right now."""
    ceiling = product.max_amount
    if product.max_savings_multiple:
        ceiling = min(ceiling, (eligible_savings(member) * product.max_savings_multiple).quantize(Decimal("0.01")))
    limit = borrowing_limit(member)
    if limit is not None:
        ceiling = min(ceiling, limit - current_borrowing(member, exclude_application=exclude_application))
    return max(ceiling, ZERO)


def _check(code, label, passed, detail, hard=True):
    return {"code": code, "label": label, "passed": bool(passed), "detail": detail, "hard": hard}


def evaluate(member, product, *, amount=None, term_months=None, exclude_application=None):
    """
    Returns {"eligible", "max_amount", "savings", "checks": [...]}. amount and
    term are optional so the portal can show general eligibility before the
    member fills in the form.
    """
    today = timezone.localdate()
    savings = eligible_savings(member)
    max_amount = maximum_amount(product, member, exclude_application=exclude_application)
    checks = [
        _check("product_active", "Loan product is available", product.is_active, "" if product.is_active else "This product is closed to new applications."),
        _check("full_member", "Applicant is a member of the cooperative", member.is_full_member,
               "" if member.is_full_member else "Christmas savers are not members and cannot borrow."),
        _check("member_active", "Membership is active", member.status == MemberStatus.ACTIVE, f"Membership status: {member.get_status_display()}."),
    ]

    months = months_of_membership(member, today)
    if product.min_membership_months:
        checks.append(_check(
            "membership_age",
            f"At least {product.min_membership_months} months of membership",
            months >= product.min_membership_months,
            f"Member for {max(months, 0)} month(s).",
        ))

    running = Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES + [Loan.Status.PENDING_DISBURSEMENT])
    defaulted = running.filter(status=Loan.Status.DEFAULTED).exists()
    checks.append(_check("no_default", "No defaulted loans", not defaulted, "A loan is in default." if defaulted else ""))

    same_product = running.filter(product=product).count()
    checks.append(_check(
        "active_loan_limit",
        f"At most {product.max_active_loans} running {product.name} loan(s)",
        same_product < product.max_active_loans,
        f"{same_product} running.",
    ))

    open_apps = LoanApplication.objects.filter(member=member, product=product, status__in=OPEN_APPLICATION_STATUSES)
    if exclude_application is not None:
        open_apps = open_apps.exclude(pk=exclude_application.pk)
    has_open = open_apps.exists()
    checks.append(_check("no_open_application", "No other open application for this product", not has_open,
                         "Another application is already in progress." if has_open else ""))

    limit = borrowing_limit(member)
    if limit is not None:
        borrowed = current_borrowing(member, exclude_application=exclude_application)
        multiple = CooperativeSettings.load().loan_savings_multiple.normalize()
        checks.append(_check(
            "borrowing_limit",
            f"Total borrowing within {multiple}× Regular Savings",
            amount is None or borrowed + amount <= limit,
            f"Regular Savings ₦{savings:,.2f}; limit ₦{limit:,.2f}; already owed ₦{borrowed:,.2f}; "
            f"available ₦{max(limit - borrowed, ZERO):,.2f}.",
        ))
    if product.max_savings_multiple:
        product_limit = (savings * product.max_savings_multiple).quantize(Decimal("0.01"))
        checks.append(_check(
            "savings_security",
            f"Loan within {product.max_savings_multiple.normalize()}× Regular Savings for this product",
            amount is None or amount <= product_limit,
            f"Regular Savings ₦{savings:,.2f}; this product lends up to ₦{product_limit:,.2f}.",
        ))

    if amount is not None:
        checks.append(_check(
            "amount_range",
            f"Amount between ₦{product.min_amount:,.2f} and ₦{product.max_amount:,.2f}",
            product.min_amount <= amount <= product.max_amount,
            f"Requested ₦{amount:,.2f}.",
        ))
    if term_months is not None:
        allowed = product.allowed_terms or None
        in_range = product.min_term_months <= term_months <= product.max_term_months
        ok = in_range and (allowed is None or term_months in allowed)
        label = (f"Term of {', '.join(map(str, allowed))} months" if allowed
                 else f"Term between {product.min_term_months} and {product.max_term_months} months")
        checks.append(_check("term", label, ok, f"Requested {term_months} months."))

    return {
        "eligible": all(c["passed"] for c in checks if c["hard"]),
        "max_amount": max_amount,
        "savings": savings,
        "checks": checks,
    }


def hard_failures(result):
    return [c for c in result["checks"] if c["hard"] and not c["passed"]]
