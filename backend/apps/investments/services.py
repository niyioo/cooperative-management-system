"""
Investment schemes and member investment accounts. A member's principal is
derived from the ledger (contributions and opening balances minus liquidations).
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.dates import months_between
from apps.common.exceptions import DomainError
from apps.common.money import to_money
from apps.ledger import services as ledger
from apps.ledger.choices import TransactionType
from apps.ledger.hooks import on_posted, on_reversed
from apps.members.models import MemberStatus

from .models import InvestmentAccount, InvestmentProduct, InvestmentReturn

PRODUCT_FIELDS = ["name", "code", "description", "min_amount", "lock_in_months", "dividend_eligible", "allow_officer_liquidation", "is_active"]
BLOCKED_MEMBER_STATUSES = {MemberStatus.INACTIVE, MemberStatus.CLOSED}


def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


# ---------------------------------------------------------------------------
# Products and returns
# ---------------------------------------------------------------------------

def _assert_unique(name, code, exclude_pk=None):
    qs = InvestmentProduct.objects.exclude(pk=exclude_pk) if exclude_pk else InvestmentProduct.objects.all()
    if qs.filter(name__iexact=name).exists():
        _field_error("name", "An investment product with this name already exists.", "duplicate_name")
    if qs.filter(code__iexact=code).exists():
        _field_error("code", "An investment product with this code already exists.", "duplicate_code")


@transaction.atomic
def create_product(actor, **data):
    require_perm(actor, P.MANAGE_INVESTMENT_PRODUCTS)
    _assert_unique(data["name"], data["code"])
    product = InvestmentProduct.objects.create(**data)
    record("investment.product_created", actor=actor, obj=product)
    return product


@transaction.atomic
def update_product(actor, product, **data):
    require_perm(actor, P.MANAGE_INVESTMENT_PRODUCTS)
    _assert_unique(data.get("name", product.name), data.get("code", product.code), exclude_pk=product.pk)
    changes = {}
    for field in PRODUCT_FIELDS:
        if field in data and getattr(product, field) != data[field]:
            changes[field] = [getattr(product, field), data[field]]
            setattr(product, field, data[field])
    if changes:
        product.save()
        record("investment.product_updated", actor=actor, obj=product, changes=changes)
    return product


@transaction.atomic
def record_return(actor, *, product, financial_year, amount_earned, description=""):
    """Scheme-level earnings, for reporting and for sizing the year's dividend."""
    require_perm(actor, P.POST_INVESTMENT_TRANSACTION)
    entry = InvestmentReturn.objects.create(
        product=product, financial_year=financial_year, amount_earned=to_money(amount_earned),
        description=description, recorded_by=actor,
    )
    record("investment.return_recorded", actor=actor, obj=entry, metadata={"amount": entry.amount_earned, "year": financial_year})
    return entry


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def account_problem(member, product):
    if not product.is_active:
        return f"{product.name} is not open to new investments."
    if member.status in BLOCKED_MEMBER_STATUSES:
        return f"{member.get_status_display()} members cannot invest."
    return None


def find_or_open_account(member, product, *, create):
    """The member's active account in a product; opened on demand when create=True."""
    account = InvestmentAccount.objects.filter(member=member, product=product, status=InvestmentAccount.Status.ACTIVE).first()
    if account is None:
        account = InvestmentAccount(member=member, product=product)
        if create:
            account.save()
    return account


@transaction.atomic
def open_account(actor, *, member, product):
    require_perm(actor, P.MANAGE_INVESTMENT_ACCOUNTS)
    assert_not_self(actor, member, "open investments for")
    problem = account_problem(member, product)
    if problem:
        raise DomainError(problem, code="not_eligible")
    account = find_or_open_account(member, product, create=False)
    if not account._state.adding:  # UUID pks are set before saving, so check the saved state
        raise DomainError(f"{member.full_name} already has an active {product.name} account.", code="account_exists")
    account.save()
    record("investment.account_opened", actor=actor, obj=account, metadata={"member": member.membership_number})
    return account


def contribution_problems(account, amount):
    problems = []
    problem = account_problem(account.member, account.product)
    if problem:
        problems.append(problem)
    if not account._state.adding and account.status != InvestmentAccount.Status.ACTIVE:
        problems.append(f"The account is {account.get_status_display().lower()}.")
    if amount < account.product.min_amount:
        problems.append(f"The minimum {account.product.name} contribution is ₦{account.product.min_amount:,.2f}.")
    return problems


@transaction.atomic
def post_contribution(actor, *, account, amount, value_date=None, description="", external_reference=""):
    require_perm(actor, P.POST_INVESTMENT_TRANSACTION)
    account = ledger.lock_account(account)
    assert_not_self(actor, account.member, "post investments for")
    amount = to_money(amount)
    problems = contribution_problems(account, amount)
    if problems:
        raise DomainError(problems[0], code="contribution_rejected", fields={"non_field_errors": problems})
    return ledger.create_entry(
        actor,
        member=account.member,
        txn_type=TransactionType.INVESTMENT_CONTRIBUTION,
        amount=amount,
        account=account,
        value_date=value_date,
        description=description or f"{account.product.name} contribution",
        external_reference=external_reference,
    )


@transaction.atomic
def liquidate(actor, *, account, amount, reason, value_date=None):
    """Return principal to the member. Only for products that allow it, after any lock-in."""
    require_perm(actor, P.POST_INVESTMENT_TRANSACTION)
    account = ledger.lock_account(account)
    assert_not_self(actor, account.member, "liquidate investments for")
    product = account.product
    if not product.allow_officer_liquidation:
        raise DomainError(f"{product.name} does not allow liquidation.", code="liquidation_not_allowed")
    if account.status != InvestmentAccount.Status.ACTIVE:
        raise DomainError(f"The account is {account.get_status_display().lower()}.", code="account_not_active")
    if product.lock_in_months:
        held = months_between(account.opened_on, timezone.localdate())
        if held < product.lock_in_months:
            raise DomainError(
                f"{product.name} is locked in for {product.lock_in_months} months; this account is {max(held, 0)} month(s) old.",
                code="locked_in",
            )
    if not (reason or "").strip():
        _field_error("reason", "Please give a reason.", "reason_required")
    amount = to_money(amount)
    ledger.assert_sufficient_balance(account, amount)
    return ledger.create_entry(
        actor,
        member=account.member,
        txn_type=TransactionType.INVESTMENT_LIQUIDATION,
        amount=amount,
        account=account,
        value_date=value_date,
        description=reason.strip(),
    )


@on_posted(TransactionType.INVESTMENT_LIQUIDATION)
def _close_when_empty(entry):
    account = InvestmentAccount.objects.select_for_update().get(pk=entry.investment_account_id)
    if ledger.posted_balance(account) == 0 and account.status == InvestmentAccount.Status.ACTIVE:
        account.status = InvestmentAccount.Status.LIQUIDATED
        account.closed_on = entry.value_date
        account.save(update_fields=["status", "closed_on", "updated_at"])
        record("investment.account_liquidated", actor=entry.approved_by or entry.created_by, obj=account)


@on_reversed(TransactionType.INVESTMENT_LIQUIDATION)
def _reopen_after_reversal(original):
    account = InvestmentAccount.objects.select_for_update().get(pk=original.investment_account_id)
    if account.status != InvestmentAccount.Status.LIQUIDATED:
        return
    if InvestmentAccount.objects.filter(member=account.member, product=account.product, status=InvestmentAccount.Status.ACTIVE).exists():
        raise DomainError(
            "The member has since opened another account in this product; move the funds with an adjustment instead.",
            code="account_replaced",
        )
    account.status = InvestmentAccount.Status.ACTIVE
    account.closed_on = None
    account.save(update_fields=["status", "closed_on", "updated_at"])
    record("investment.account_reopened", obj=account, metadata={"reversed_liquidation": original.reference})
