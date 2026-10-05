"""
Loan eligibility (BR-22). One function produces the list of checks shown to
the member before applying, stored as a snapshot at submission, and re-run
with the approved amount at approval. Hard failures block; soft ones warn.
"""
from decimal import Decimal

from django.utils import timezone

from apps.ledger.selectors import ZERO, net_by
from apps.members.models import MemberStatus
from apps.savings.models import SavingsAccount
from apps.savings.rules import months_of_membership

from .models import Loan, LoanApplication

OPEN_APPLICATION_STATUSES = [
    LoanApplication.Status.SUBMITTED,
    LoanApplication.Status.UNDER_REVIEW,
    LoanApplication.Status.RETURNED,
    LoanApplication.Status.APPROVED,
]


def eligible_savings(member):
    """Savings that count as security: products flagged counts_toward_loan_eligibility, accounts not closed."""
    accounts = SavingsAccount.objects.filter(
        member=member, product__counts_toward_loan_eligibility=True
    ).exclude(status=SavingsAccount.Status.CLOSED)
    balances = net_by("savings_account", member=member)
    return sum((balances.get(a.pk, ZERO) for a in accounts), ZERO)


def maximum_amount(product, member):
    """The most this member could borrow on this product right now."""
    ceiling = product.max_amount
    if product.max_savings_multiple:
        ceiling = min(ceiling, (eligible_savings(member) * product.max_savings_multiple).quantize(Decimal("0.01")))
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
    max_amount = maximum_amount(product, member)
    checks = [
        _check("product_active", "Loan product is available", product.is_active, "" if product.is_active else "This product is closed to new applications."),
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

    if product.max_savings_multiple:
        checks.append(_check(
            "savings_security",
            f"Loan within {product.max_savings_multiple.normalize()}× eligible savings",
            amount is None or amount <= max_amount,
            f"Eligible savings ₦{savings:,.2f}; maximum loan ₦{max_amount:,.2f}.",
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
