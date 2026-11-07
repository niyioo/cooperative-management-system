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
from apps.savings.statutory import positions, statutory_account

from .calculators import end_month_deadline, longest_term_before, schedule_for_product
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


def savings_multiple(product, member):
    """The savings multiple this member may borrow on this product: officials may have more (BR-37)."""
    if member.is_official and product.official_savings_multiple:
        return product.official_savings_multiple
    return product.max_savings_multiple


def running_loans(member, exclude_application=None):
    """Loans held or granted: running, awaiting disbursement, or approved and not yet paid out (BR-37)."""
    count = Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES + [Loan.Status.PENDING_DISBURSEMENT]).count()
    approved = LoanApplication.objects.filter(member=member, status=LoanApplication.Status.APPROVED, loans__isnull=True)
    if exclude_application is not None:
        approved = approved.exclude(pk=exclude_application.pk)
    return count + approved.count()


def monthly_commitments(member):
    """
    What the member already pays each month: the next instalment of every running loan
    plus their monthly savings contribution. Shown to officers against net pay (BR-37).
    """
    total = ZERO
    for loan in Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES).prefetch_related("installments"):
        upcoming = [i for i in loan.installments.all() if i.due_date >= timezone.localdate()]
        instalment = (upcoming or list(loan.installments.all()))[:1]
        total += sum((i.principal_due + i.interest_due for i in instalment), ZERO)
    account = statutory_account(member)
    if account is not None:
        total += positions([account])[account.pk]["amount"]
    return total


def maximum_amount(product, member, exclude_application=None):
    """The most this member could borrow on this product right now."""
    ceiling = product.max_amount
    multiple = savings_multiple(product, member)
    if multiple:
        ceiling = min(ceiling, (eligible_savings(member) * multiple).quantize(Decimal("0.01")))
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
    member_ok = member.is_full_member or product.open_to_non_members
    checks = [
        _check("product_active", "Loan product is available", product.is_active, "" if product.is_active else "This product is closed to new applications."),
        _check("full_member", "Applicant is a member of the cooperative" if not product.open_to_non_members
               else "Open to members and Christmas savers", member_ok,
               "" if member_ok else "Christmas savers are not members and cannot borrow on this product."),
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

    most = CooperativeSettings.load().max_running_loans
    if most:
        held = running_loans(member, exclude_application=exclude_application)
        checks.append(_check(
            "running_loan_limit",
            f"At most {most} loans at once",
            held < most,
            f"{held} loan(s) held or approved.",
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
    multiple = savings_multiple(product, member)
    if multiple:
        product_limit = (savings * multiple).quantize(Decimal("0.01"))
        who = "officials" if member.is_official and product.official_savings_multiple else "members"
        checks.append(_check(
            "savings_security",
            f"Loan within {multiple.normalize()}× Regular Savings ({who})",
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
        if product.must_end_by_month:
            deadline = end_month_deadline(today, product.must_end_by_month)
            longest = longest_term_before(today, product.must_end_by_month)
            checks.append(_check(
                "end_month",
                f"Repaid by {deadline:%B %Y}",
                term_months <= longest,
                f"Paid out now, at most {longest} monthly instalment(s) fit before {deadline:%d %B %Y}.",
            ))
    if amount is not None and term_months is not None and amount > 0 and term_months >= 1:
        instalment = schedule_for_product(product, amount, term_months, today).monthly_payment
        commitments = monthly_commitments(member)
        pay = member.monthly_net_pay
        detail = (f"New instalment ₦{instalment:,.2f}; already paying ₦{commitments:,.2f} a month; "
                  + (f"net pay ₦{pay:,.2f}." if pay else "net pay not recorded."))
        checks.append(_check("pay_covers", "Monthly pay covers the deductions (officers decide)",
                             pay is None or instalment + commitments <= pay, detail, hard=False))

    return {
        "eligible": all(c["passed"] for c in checks if c["hard"]),
        "max_amount": max_amount,
        "savings": savings,
        "checks": checks,
    }


def hard_failures(result):
    return [c for c in result["checks"] if c["hard"] and not c["passed"]]
