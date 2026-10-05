"""
Contribution rules, shared by single postings and batch uploads so both apply
exactly the same checks (BR-02, BR-03, BR-26).
"""
import calendar
from datetime import date

from django.utils import timezone

from apps.common.dates import months_between
from apps.ledger.choices import TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.models import MemberStatus

from .models import ProductKind, SavingsAccount, SavingsCycle

BLOCKED_MEMBER_STATUSES = {MemberStatus.INACTIVE, MemberStatus.CLOSED}


def month_start(value):
    return value.replace(day=1)


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


def cycle_months(cycle):
    months, current = [], cycle.start_date.replace(day=1)
    while current <= cycle.end_date:
        months.append(current)
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return months


def months_of_membership(member, on_date=None):
    return months_between(member.date_joined, on_date or timezone.localdate())


def eligibility_problem(product, member, on_date=None):
    if member.status in BLOCKED_MEMBER_STATUSES:
        return f"{member.get_status_display()} members cannot save into {product.name}."
    if product.min_membership_months and months_of_membership(member, on_date) < product.min_membership_months:
        return f"{product.name} requires at least {product.min_membership_months} months of membership."
    return None


def resolve_account(member, product, period, *, create=False):
    """
    Find the account a contribution for `period` belongs to. Returns
    (account, problem). With create=False a missing account is returned
    unsaved so rules can still be checked during a dry run.
    """
    if product.kind == ProductKind.REGULAR:
        account = SavingsAccount.objects.filter(member=member, product=product, cycle__isnull=True).first()
        if account is None:
            account = SavingsAccount(member=member, product=product)
            if create:
                account.save()
        return account, None

    if period is None:
        return None, f"A contribution month is required for {product.name}."
    cycle = SavingsCycle.objects.filter(product=product, year=period.year).first()
    if cycle is None:
        return None, f"There is no {product.name} cycle for {period.year}."
    account = SavingsAccount.objects.filter(member=member, cycle=cycle).first()
    if account is None:
        problem = eligibility_problem(product, member)
        if problem:
            return None, problem
        account = SavingsAccount(member=member, product=product, cycle=cycle)
        if create:
            account.save()
    return account, None


def contribution_problems(account, amount, period, *, ignore_batch=None):
    """Everything that would stop this contribution being accepted. Empty list = OK."""
    problems = []
    member, product = account.member, account.product

    if member.status in BLOCKED_MEMBER_STATUSES:
        problems.append(f"{member.get_status_display()} members cannot receive contributions.")
    if not product.is_active:
        problems.append(f"{product.name} is no longer active.")
    if account.status != SavingsAccount.Status.ACTIVE:
        problems.append(f"The {product.name} account is {account.get_status_display().lower()}.")
    if amount < product.min_contribution:
        problems.append(f"The minimum {product.name} contribution is ₦{product.min_contribution:,.2f}.")

    if product.kind == ProductKind.CYCLE:
        cycle = account.cycle
        if cycle.status != SavingsCycle.Status.OPEN:
            problems.append(f"{cycle} is {cycle.get_status_display().lower()}, not open for contributions.")
        if period is None:
            problems.append(f"A contribution month is required for {product.name}.")
        elif product.allow_contribution_outside_window:
            if period.year != cycle.year:
                problems.append(f"{period:%B %Y} is not in {cycle}.")
        elif not (cycle.start_date <= period <= cycle.end_date):
            problems.append(
                f"{period:%B %Y} is outside the {cycle} contribution window "
                f"({cycle.start_date:%B}–{cycle.end_date:%B})."
            )

    if period and not product.allow_multiple_contributions_per_period and not account._state.adding:
        existing = Transaction.objects.filter(
            savings_account=account,
            period=period,
            txn_type=TransactionType.SAVINGS_CONTRIBUTION,
            status__in=[TransactionStatus.POSTED, TransactionStatus.PENDING],
        )
        if ignore_batch is not None:
            existing = existing.exclude(batch=ignore_batch)
        if existing.exists():
            problems.append(f"A {product.name} contribution for {period:%B %Y} has already been recorded.")
    return problems
