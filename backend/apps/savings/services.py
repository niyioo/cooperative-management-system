"""
Savings products, Christmas Savings cycles, accounts and postings
(ARCHITECTURE.md §6.3). Members can never withdraw through the portal (BR-01);
officer withdrawals only exist for products that explicitly allow them.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.ledger import services as ledger
from apps.ledger.choices import BatchStatus, BatchType, TransactionType
from apps.ledger.models import Transaction, TransactionBatch
from apps.ledger.selectors import with_balance
from apps.members.models import Member, MemberStatus

from . import statutory
from .models import MonthlyContributionChange, ProductKind, SavingsAccount, SavingsCycle, SavingsProduct
from .rules import contribution_problems, eligibility_problem, month_end, month_start, resolve_account

PRODUCT_FIELDS = [
    "name",
    "code",
    "description",
    "kind",
    "cycle_start_month",
    "cycle_end_month",
    "payout_month",
    "expected_monthly_contribution",
    "min_contribution",
    "max_monthly_contribution",
    "allow_contribution_outside_window",
    "allow_multiple_contributions_per_period",
    "min_membership_months",
    "is_mandatory",
    "allow_officer_withdrawal",
    "allow_member_withdrawal_request",
    "counts_toward_loan_eligibility",
    "is_active",
    "display_order",
]


def _diff_and_apply(obj, data, fields):
    changes = {}
    for field in fields:
        if field in data and getattr(obj, field) != data[field]:
            changes[field] = [getattr(obj, field), data[field]]
            setattr(obj, field, data[field])
    return changes


def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def _validate_product(data):
    if data.get("kind") == ProductKind.CYCLE:
        if not data.get("cycle_start_month") or not data.get("cycle_end_month"):
            _field_error("cycle_start_month", "Cycle products need a start and end month.", "cycle_months_required")
        if data["cycle_start_month"] > data["cycle_end_month"]:
            _field_error("cycle_end_month", "The cycle must end in the same year it starts.", "invalid_cycle_window")
    else:
        data["cycle_start_month"] = data["cycle_end_month"] = data["payout_month"] = None
    maximum = data.get("max_monthly_contribution")
    if maximum is not None and maximum < (data.get("min_contribution") or 0):
        _field_error("max_monthly_contribution", "The maximum cannot be below the minimum contribution.", "invalid_maximum")
    if data.get("allow_member_withdrawal_request") and not data.get("allow_officer_withdrawal"):
        _field_error(
            "allow_member_withdrawal_request",
            "Member withdrawal requests need officer withdrawals to be allowed too.",
            "invalid_withdrawal_settings",
        )


def _assert_unique_product(name, code, exclude_pk=None):
    qs = SavingsProduct.objects.exclude(pk=exclude_pk) if exclude_pk else SavingsProduct.objects.all()
    if qs.filter(name__iexact=name).exists():
        _field_error("name", "A savings product with this name already exists.", "duplicate_name")
    if qs.filter(code__iexact=code).exists():
        _field_error("code", "A savings product with this code already exists.", "duplicate_code")


@transaction.atomic
def create_product(actor, **data):
    require_perm(actor, P.MANAGE_SAVINGS_PRODUCTS)
    _validate_product(data)
    _assert_unique_product(data["name"], data["code"])
    product = SavingsProduct.objects.create(**data)
    record("savings.product_created", actor=actor, obj=product)
    return product


@transaction.atomic
def update_product(actor, product, **data):
    require_perm(actor, P.MANAGE_SAVINGS_PRODUCTS)
    if "kind" in data and data["kind"] != product.kind and product.accounts.exists():
        _field_error("kind", "The kind cannot change once accounts exist.", "kind_locked")
    merged = {f: data.get(f, getattr(product, f)) for f in PRODUCT_FIELDS}
    _validate_product(merged)
    _assert_unique_product(merged["name"], merged["code"], exclude_pk=product.pk)
    old_minimum = product.min_contribution
    changes = _diff_and_apply(product, merged, PRODUCT_FIELDS)
    if changes:
        product.save()
        record("savings.product_updated", actor=actor, obj=product, changes=changes)
        if "min_contribution" in changes:
            statutory.minimum_changed(actor, product, old_minimum)
    return product


# ---------------------------------------------------------------------------
# Cycles (Christmas Savings)
# ---------------------------------------------------------------------------

@transaction.atomic
def create_cycle(actor, *, product, year, expected_monthly_contribution=None):
    require_perm(actor, P.MANAGE_SAVINGS_CYCLES)
    if product.kind != ProductKind.CYCLE:
        _field_error("product", f"{product.name} is not a cycle product.", "not_cycle_product")
    if not product.is_active:
        _field_error("product", f"{product.name} is not active.", "inactive_product")
    if SavingsCycle.objects.filter(product=product, year=year).exists():
        _field_error("year", f"{product.name} {year} already exists.", "duplicate_cycle")
    cycle = SavingsCycle.objects.create(
        product=product,
        year=year,
        start_date=date(year, product.cycle_start_month, 1),
        end_date=month_end(year, product.cycle_end_month),
        expected_monthly_contribution=(
            product.expected_monthly_contribution if expected_monthly_contribution is None else expected_monthly_contribution
        ),
    )
    record("savings.cycle_created", actor=actor, obj=cycle)
    return cycle


@transaction.atomic
def update_cycle(actor, cycle, *, expected_monthly_contribution):
    require_perm(actor, P.MANAGE_SAVINGS_CYCLES)
    if cycle.status != SavingsCycle.Status.UPCOMING:
        raise DomainError("The expected contribution can only change before the cycle opens.", code="cycle_started")
    changes = _diff_and_apply(cycle, {"expected_monthly_contribution": expected_monthly_contribution}, ["expected_monthly_contribution"])
    if changes:
        cycle.save()
        record("savings.cycle_updated", actor=actor, obj=cycle, changes=changes)
    return cycle


@transaction.atomic
def open_cycle(actor, cycle):
    """Open the cycle and give every eligible member an account in it."""
    require_perm(actor, P.MANAGE_SAVINGS_CYCLES)
    cycle = SavingsCycle.objects.select_for_update(of=("self",)).select_related("product").get(pk=cycle.pk)
    if cycle.status != SavingsCycle.Status.UPCOMING:
        raise DomainError(f"{cycle} has already been opened.", code="invalid_cycle_status")
    still_open = SavingsCycle.objects.filter(product=cycle.product, status=SavingsCycle.Status.OPEN).first()
    if still_open:
        raise DomainError(f"Close {still_open} before opening {cycle}.", code="previous_cycle_open")

    cycle.status = SavingsCycle.Status.OPEN
    cycle.opened_by = actor
    cycle.opened_at = timezone.now()
    cycle.save(update_fields=["status", "opened_by", "opened_at", "updated_at"])

    have_account = set(cycle.accounts.values_list("member_id", flat=True))
    new_accounts = [
        SavingsAccount(member=member, product=cycle.product, cycle=cycle)
        for member in Member.objects.filter(status=MemberStatus.ACTIVE).exclude(pk__in=have_account)
        if eligibility_problem(cycle.product, member) is None  # judged on the day accounts open
    ]
    for account in new_accounts:
        account.save()  # save() assigns account numbers, so no bulk_create
    record("savings.cycle_opened", actor=actor, obj=cycle, metadata={"accounts_opened": len(new_accounts)})
    return cycle, len(new_accounts)


@transaction.atomic
def close_cycle(actor, cycle):
    require_perm(actor, P.CLOSE_SAVINGS_CYCLE)
    cycle = SavingsCycle.objects.select_for_update().get(pk=cycle.pk)
    if cycle.status != SavingsCycle.Status.OPEN:
        raise DomainError(f"{cycle} is not open.", code="invalid_cycle_status")
    if Transaction.objects.pending().filter(savings_account__cycle=cycle).exists():
        raise DomainError(
            f"{cycle} still has contributions awaiting approval. Approve or reject them first.",
            code="pending_entries",
        )
    cycle.status = SavingsCycle.Status.CLOSED
    cycle.closed_by = actor
    cycle.closed_at = timezone.now()
    cycle.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    record("savings.cycle_closed", actor=actor, obj=cycle)
    return cycle


def open_payout_batch(cycle):
    return TransactionBatch.objects.filter(
        batch_type=BatchType.CYCLE_PAYOUTS,
        status__in=[BatchStatus.VALIDATED, BatchStatus.SUBMITTED],
        validation_report__cycle_id=str(cycle.pk),
    ).first()


@transaction.atomic
def prepare_cycle_payout(actor, cycle, *, value_date=None, description=""):
    """
    Build a payout batch: one SAVINGS_CYCLE_PAYOUT per account with a balance.
    Another officer approves the batch; posting it marks the cycle PAID_OUT.
    """
    require_perm(actor, P.MANAGE_BATCHES, P.POST_SAVINGS_WITHDRAWAL)
    cycle = SavingsCycle.objects.select_for_update(of=("self",)).select_related("product").get(pk=cycle.pk)
    if cycle.status != SavingsCycle.Status.CLOSED:
        raise DomainError(f"{cycle} must be closed before it is paid out.", code="invalid_cycle_status")
    if open_payout_batch(cycle):
        raise DomainError(f"A payout batch for {cycle} is already awaiting approval.", code="payout_in_progress")

    accounts = with_balance(cycle.accounts.select_related("member"), "savings_account").filter(balance__gt=0)

    def build(batch):
        batch.validation_report = {"cycle_id": str(cycle.pk)}
        for account in accounts:
            ledger.create_entry(
                actor,
                member=account.member,
                txn_type=TransactionType.SAVINGS_CYCLE_PAYOUT,
                amount=account.balance,
                account=account,
                value_date=value_date,
                description=description or f"{cycle} payout",
                batch=batch,
                audit=False,
            )

    batch = ledger.create_batch_from_entries(
        actor,
        batch_type=BatchType.CYCLE_PAYOUTS,
        build_lines=build,
        description=description or f"{cycle} payout",
    )
    return batch


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@transaction.atomic
def open_account(actor, *, member, product, year=None, elected_monthly_amount=None):
    require_perm(actor, P.POST_SAVINGS_CONTRIBUTION)
    assert_not_self(actor, member, "open accounts for")
    if not product.is_active:
        _field_error("product", f"{product.name} is not active.", "inactive_product")
    problem = eligibility_problem(product, member)
    if problem:
        raise DomainError(problem, code="not_eligible")
    if product.kind == ProductKind.CYCLE:
        if year is None:
            _field_error("year", "Choose the cycle year.", "year_required")
        account, problem = resolve_account(member, product, date(year, product.cycle_start_month, 1))
        if problem:
            raise DomainError(problem, code="no_cycle")
    else:
        account, _ = resolve_account(member, product, None)
    if not account._state.adding:  # UUID pks are set before saving, so check the saved state
        raise DomainError(f"{member.full_name} already has this account ({account.account_number}).", code="account_exists")
    if elected_monthly_amount is not None and statutory.is_statutory(account):
        problem = statutory.amount_problem(product, elected_monthly_amount)
        if problem:
            _field_error("elected_monthly_amount", *problem)
    account.elected_monthly_amount = elected_monthly_amount
    account.save()
    if elected_monthly_amount and statutory.is_statutory(account):
        MonthlyContributionChange.objects.create(
            account=account,
            amount=elected_monthly_amount,
            effective_from=month_start(account.opened_on),
            changed_by=actor,
            reason="Chosen when the account was opened",
        )
    record("savings.account_opened", actor=actor, obj=account, metadata={"member": member.membership_number})
    return account


@transaction.atomic
def update_account(actor, account, **data):
    require_perm(actor, P.POST_SAVINGS_CONTRIBUTION)
    assert_not_self(actor, account.member, "change accounts for")
    if account.status == SavingsAccount.Status.CLOSED:
        raise DomainError("This account is closed.", code="account_closed")
    if data.get("status") not in (None, SavingsAccount.Status.ACTIVE, SavingsAccount.Status.FROZEN):
        _field_error("status", "Accounts can only be set to Active or Frozen here.", "invalid_status")
    if "elected_monthly_amount" in data and statutory.is_statutory(account):
        # The statutory amount has a history (it judges arrears), so it changes from this month on.
        amount = data.pop("elected_monthly_amount")
        if amount is None:
            _field_error("elected_monthly_amount", "The monthly contribution cannot be blank.", "amount_required")
        if amount != statutory.position(account)["amount"]:
            statutory.set_monthly_contribution(actor, account, amount=amount)
            account.refresh_from_db()
    changes = _diff_and_apply(account, data, ["elected_monthly_amount", "status"])
    if changes:
        account.save()
        record("savings.account_updated", actor=actor, obj=account, changes=changes)
    return account


# ---------------------------------------------------------------------------
# Postings
# ---------------------------------------------------------------------------

@transaction.atomic
def post_contribution(actor, *, account, amount, period=None, value_date=None, description="", external_reference=""):
    require_perm(actor, P.POST_SAVINGS_CONTRIBUTION)
    account = ledger.lock_account(account)
    assert_not_self(actor, account.member, "post contributions to")
    value_date = value_date or timezone.localdate()
    if period is None and account.product.kind == ProductKind.REGULAR:
        period = month_start(value_date)
    problems = contribution_problems(account, amount, period)
    if problems:
        raise DomainError(problems[0], code="contribution_rejected", fields={"non_field_errors": problems})
    return ledger.create_entry(
        actor,
        member=account.member,
        txn_type=TransactionType.SAVINGS_CONTRIBUTION,
        amount=amount,
        account=account,
        value_date=value_date,
        period=period,
        description=description or f"{account.product.name} contribution {period:%b %Y}",
        external_reference=external_reference,
    )


@transaction.atomic
def post_withdrawal(actor, *, account, amount, reason, value_date=None):
    """Officer-only, and only for products configured to allow it. Off for every EMDI product."""
    require_perm(actor, P.POST_SAVINGS_WITHDRAWAL)
    account = ledger.lock_account(account)
    assert_not_self(actor, account.member, "post withdrawals from")
    if not account.product.allow_officer_withdrawal:
        raise DomainError(f"Withdrawals are not permitted from {account.product.name}.", code="withdrawal_not_allowed")
    if account.status != SavingsAccount.Status.ACTIVE:
        raise DomainError(f"The account is {account.get_status_display().lower()}.", code="account_not_active")
    if not (reason or "").strip():
        _field_error("reason", "Please give a reason.", "reason_required")
    ledger.assert_sufficient_balance(account, amount)
    return ledger.create_entry(
        actor,
        member=account.member,
        txn_type=TransactionType.SAVINGS_WITHDRAWAL,
        amount=amount,
        account=account,
        value_date=value_date,
        description=reason.strip(),
    )
