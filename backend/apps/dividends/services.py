"""
Annual dividend cycles (ARCHITECTURE.md §6.5, BR-25).

DRAFT -> CALCULATED -> APPROVED -> PUBLISHED -> PAID   (CANCELLED before approval)

Every calculation is a new run; earlier draft runs are kept as SUPERSEDED, so
no calculated figure is ever silently changed. Approval (by someone other than
whoever ran the calculation) locks one run. Members only see a cycle once it
is PUBLISHED. Payment is a batch that a second officer approves.
"""
from datetime import date

from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from apps.accounts.permissions import require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.serializers import money_to_str
from apps.configuration.models import CooperativeSettings
from apps.investments.models import InvestmentProduct
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchStatus, BatchType, TransactionType
from apps.ledger.hooks import on_posted
from apps.ledger.models import TransactionBatch
from apps.savings.models import ProductKind, SavingsAccount, SavingsProduct
from apps.notifications import services as notifications

from .calculation import dividend_amounts, member_bases
from .models import DividendCalculationRun, DividendCycle, MemberDividend

CYCLE = DividendCycle.Status
RUN = DividendCalculationRun.Status
EDITABLE_FIELDS = [
    "basis",
    "cutoff_date",
    "rate",
    "distributable_surplus",
    "withholding_rate",
    "payment_method",
    "credit_savings_product",
    "notes",
]


def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


def _lock(cycle):
    return DividendCycle.objects.select_for_update().get(pk=cycle.pk)


def _assert_status(cycle, allowed, action):
    if cycle.status not in allowed:
        raise DomainError(f"A {cycle.get_status_display().lower()} dividend cycle cannot be {action}.", code="invalid_cycle_status")


def _validate(data, year):
    cutoff = data.get("cutoff_date")
    if cutoff and cutoff.year != year:
        _field_error("cutoff_date", f"The cutoff date must fall in {year}.", "invalid_cutoff")
    if data.get("payment_method") == DividendCycle.PaymentMethod.CREDIT_TO_SAVINGS:
        product = data.get("credit_savings_product")
        if product is None:
            _field_error("credit_savings_product", "Choose the savings product dividends are credited to.", "credit_product_required")
        if product.kind != ProductKind.REGULAR:
            _field_error("credit_savings_product", "Dividends can only be credited to a regular savings product.", "invalid_credit_product")


# ---------------------------------------------------------------------------
# Cycle set-up
# ---------------------------------------------------------------------------

@transaction.atomic
def create_cycle(
    actor,
    *,
    financial_year,
    rate,
    basis=DividendCycle.Basis.AVERAGE_MONTHLY_BALANCE,
    cutoff_date=None,
    eligible_investment_products=None,
    eligible_savings_products=None,
    distributable_surplus=None,
    withholding_rate=0,
    payment_method=DividendCycle.PaymentMethod.CREDIT_TO_SAVINGS,
    credit_savings_product=None,
    notes="",
):
    require_perm(actor, P.MANAGE_DIVIDEND_CYCLES)
    if DividendCycle.objects.filter(financial_year=financial_year).exclude(status=CYCLE.CANCELLED).exists():
        _field_error("financial_year", f"A dividend cycle for {financial_year} already exists.", "duplicate_cycle")
    if payment_method == DividendCycle.PaymentMethod.CREDIT_TO_SAVINGS and credit_savings_product is None:
        credit_savings_product = SavingsProduct.objects.filter(code="REGULAR").first()
    data = {
        "basis": basis,
        "cutoff_date": cutoff_date or date(financial_year, 11, 30),
        "rate": rate,
        "distributable_surplus": distributable_surplus,
        "withholding_rate": withholding_rate,
        "payment_method": payment_method,
        "credit_savings_product": credit_savings_product,
        "notes": notes,
    }
    _validate(data, financial_year)
    if eligible_investment_products is None:
        eligible_investment_products = list(InvestmentProduct.objects.filter(dividend_eligible=True))
    if not eligible_investment_products and not eligible_savings_products:
        _field_error("eligible_investment_products", "Choose at least one eligible product.", "no_eligible_products")

    cycle = DividendCycle.objects.create(financial_year=financial_year, created_by=actor, **data)
    cycle.eligible_investment_products.set(eligible_investment_products)
    cycle.eligible_savings_products.set(eligible_savings_products or [])
    record("dividend.cycle_created", actor=actor, obj=cycle, metadata=money_to_str({"rate": cycle.rate, "basis": basis}))
    return cycle


def _supersede_drafts(cycle):
    DividendCalculationRun.objects.filter(cycle=cycle, status=RUN.DRAFT).update(status=RUN.SUPERSEDED, updated_at=timezone.now())


@transaction.atomic
def update_cycle(actor, cycle, *, eligible_investment_products=None, eligible_savings_products=None, **data):
    """Parameters can change until approval; changing a calculated cycle sends it back to DRAFT."""
    require_perm(actor, P.MANAGE_DIVIDEND_CYCLES)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.DRAFT, CYCLE.CALCULATED], "edited")
    merged = {f: data.get(f, getattr(cycle, f)) for f in EDITABLE_FIELDS}
    _validate(merged, cycle.financial_year)
    changes = {}
    for field in EDITABLE_FIELDS:
        if field in data and getattr(cycle, field) != data[field]:
            changes[field] = [str(getattr(cycle, field)), str(data[field])]
            setattr(cycle, field, data[field])
    if eligible_investment_products is not None:
        changes["eligible_investment_products"] = [p.code for p in eligible_investment_products]
        cycle.eligible_investment_products.set(eligible_investment_products)
    if eligible_savings_products is not None:
        changes["eligible_savings_products"] = [p.code for p in eligible_savings_products]
        cycle.eligible_savings_products.set(eligible_savings_products)
    if changes:
        if cycle.status == CYCLE.CALCULATED:
            _supersede_drafts(cycle)
            cycle.status = CYCLE.DRAFT
        cycle.save()
        record("dividend.cycle_updated", actor=actor, obj=cycle, changes=changes)
    return cycle


@transaction.atomic
def cancel_cycle(actor, cycle, *, reason):
    require_perm(actor, P.MANAGE_DIVIDEND_CYCLES)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.DRAFT, CYCLE.CALCULATED], "cancelled")
    if not (reason or "").strip():
        _field_error("reason", "Please give a reason.", "reason_required")
    _supersede_drafts(cycle)
    cycle.status = CYCLE.CANCELLED
    cycle.save(update_fields=["status", "updated_at"])
    record("dividend.cycle_cancelled", actor=actor, obj=cycle, metadata={"reason": reason.strip()})
    return cycle


# ---------------------------------------------------------------------------
# Calculation, approval, publication
# ---------------------------------------------------------------------------

@transaction.atomic
def calculate(actor, cycle):
    """Create a new calculation run. Earlier draft runs are kept, marked SUPERSEDED."""
    require_perm(actor, P.CALCULATE_DIVIDENDS)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.DRAFT, CYCLE.CALCULATED], "recalculated")
    bases = member_bases(cycle)
    if not bases:
        raise DomainError("No member has an eligible balance for this cycle.", code="nothing_to_calculate")

    _supersede_drafts(cycle)
    run_number = (cycle.runs.aggregate(n=Max("run_number"))["n"] or 0) + 1
    run = DividendCalculationRun.objects.create(
        cycle=cycle,
        run_number=run_number,
        run_by=actor,
        parameters=money_to_str(
            {
                "basis": cycle.basis,
                "cutoff_date": cycle.cutoff_date.isoformat(),
                "rate": cycle.rate,
                "withholding_rate": cycle.withholding_rate,
                "eligible_investment_products": sorted(cycle.eligible_investment_products.values_list("code", flat=True)),
                "eligible_savings_products": sorted(cycle.eligible_savings_products.values_list("code", flat=True)),
            }
        ),
    )
    rows = []
    for member_id, info in bases.items():
        gross, withholding, net = dividend_amounts(info["basis"], cycle.rate, cycle.withholding_rate)
        rows.append(
            MemberDividend(
                run=run,
                cycle=cycle,
                member_id=member_id,
                basis_amount=info["basis"],
                rate=cycle.rate,
                gross_amount=gross,
                withholding_amount=withholding,
                net_amount=net,
                calculation_detail=money_to_str({"month_end_balances": info["balances"], "basis": cycle.basis}),
            )
        )
    MemberDividend.objects.bulk_create(rows)
    totals = MemberDividend.objects.filter(run=run).aggregate(
        basis=Sum("basis_amount"), gross=Sum("gross_amount"), withholding=Sum("withholding_amount"), net=Sum("net_amount")
    )
    if cycle.distributable_surplus is not None and totals["gross"] > cycle.distributable_surplus:
        raise DomainError(
            f"Total dividends of ₦{totals['gross']:,.2f} exceed the distributable surplus of "
            f"₦{cycle.distributable_surplus:,.2f}. Lower the rate and calculate again.",
            code="exceeds_surplus",
        )
    run.total_basis, run.total_gross = totals["basis"], totals["gross"]
    run.total_withholding, run.total_net = totals["withholding"], totals["net"]
    run.member_count = len(rows)
    run.save()
    cycle.status = CYCLE.CALCULATED
    cycle.save(update_fields=["status", "updated_at"])

    warning = None
    if timezone.localdate().month != CooperativeSettings.load().dividend_processing_month:
        warning = "Dividends are normally processed in December; this calculation was run in another month."
    record(
        "dividend.calculated",
        actor=actor,
        obj=cycle,
        metadata=money_to_str({"run": run_number, "members": run.member_count, "total_net": run.total_net, "warning": warning}),
    )
    return run, warning


def latest_draft_run(cycle):
    return cycle.runs.filter(status=RUN.DRAFT).order_by("-run_number").first()


@transaction.atomic
def approve(actor, cycle):
    """
    Lock the latest run. The approver must not be the officer who ran it
    (maker-checker at cycle level, BR-25). Officers' own dividends sit inside
    the run like everyone else's, so BR-18 is applied at this level.
    """
    require_perm(actor, P.APPROVE_DIVIDENDS)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.CALCULATED], "approved")
    run = latest_draft_run(cycle)
    if run.run_by_id == actor.pk:
        raise DomainError("You ran this calculation, so another officer must approve it.", code="maker_checker")
    run.status = RUN.APPROVED
    run.save(update_fields=["status", "updated_at"])
    MemberDividend.objects.filter(run=run).update(status=MemberDividend.Status.APPROVED, updated_at=timezone.now())
    cycle.approved_run = run
    cycle.approved_by = actor
    cycle.approved_at = timezone.now()
    cycle.status = CYCLE.APPROVED
    cycle.save()
    record("dividend.approved", actor=actor, obj=cycle, metadata=money_to_str({"run": run.run_number, "total_net": run.total_net}))
    return cycle


@transaction.atomic
def publish(actor, cycle):
    require_perm(actor, P.APPROVE_DIVIDENDS)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.APPROVED], "published")
    cycle.status = CYCLE.PUBLISHED
    cycle.published_by = actor
    cycle.published_at = timezone.now()
    cycle.save()
    record("dividend.published", actor=actor, obj=cycle)
    dividends = (
        MemberDividend.objects.filter(run_id=cycle.approved_run_id, net_amount__gt=0)
        .select_related("member")
    )
    for dividend in dividends:
        notifications.notify_member(
            dividend.member, category=notifications.Category.DIVIDEND,
            title=f"Your {cycle.financial_year} dividend",
            body=f"The {cycle.financial_year} dividend has been declared at {cycle.rate:g}%. Your dividend is {notifications.naira(dividend.net_amount)}.",
            link=notifications.link("dividends"),
        )
    return cycle


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

def open_payment_batch(cycle):
    return TransactionBatch.objects.filter(
        batch_type=BatchType.DIVIDEND_PAYMENTS,
        status__in=[BatchStatus.VALIDATED, BatchStatus.SUBMITTED],
        validation_report__dividend_cycle_id=str(cycle.pk),
    ).first()


@transaction.atomic
def prepare_payment(actor, cycle, *, value_date=None):
    """Build the payment batch (one DIVIDEND_PAYMENT per member); a second officer approves it."""
    require_perm(actor, P.PAY_DIVIDENDS, P.MANAGE_BATCHES)
    cycle = _lock(cycle)
    _assert_status(cycle, [CYCLE.PUBLISHED], "paid")
    if open_payment_batch(cycle):
        raise DomainError("A payment batch for this cycle is already awaiting approval.", code="payment_in_progress")

    dividends = MemberDividend.objects.filter(run=cycle.approved_run, status=MemberDividend.Status.APPROVED).select_related("member")
    dividends.filter(net_amount=0).update(status=MemberDividend.Status.WITHHELD, updated_at=timezone.now())
    credit = cycle.payment_method == DividendCycle.PaymentMethod.CREDIT_TO_SAVINGS

    def build(batch):
        batch.validation_report = {"dividend_cycle_id": str(cycle.pk)}
        for dividend in dividends.filter(net_amount__gt=0):
            account = None
            if credit:
                account, _ = SavingsAccount.objects.get_or_create(
                    member=dividend.member, product=cycle.credit_savings_product, cycle=None
                )
            ledger.create_entry(
                actor,
                member=dividend.member,
                txn_type=TransactionType.DIVIDEND_PAYMENT,
                amount=dividend.net_amount,
                account=account,
                value_date=value_date,
                description=f"{cycle.financial_year} dividend",
                batch=batch,
                audit=False,
            )

    return ledger.create_batch_from_entries(
        actor, batch_type=BatchType.DIVIDEND_PAYMENTS, build_lines=build, description=f"{cycle.financial_year} dividend payment"
    )


@on_posted(TransactionType.DIVIDEND_PAYMENT)
def _mark_dividend_paid(entry):
    cycle_id = entry.batch.validation_report.get("dividend_cycle_id") if entry.batch_id else None
    if not cycle_id:
        return
    cycle = DividendCycle.objects.get(pk=cycle_id)
    MemberDividend.objects.filter(run_id=cycle.approved_run_id, member_id=entry.member_id).update(
        status=MemberDividend.Status.PAID, payment_transaction=entry, paid_at=entry.posted_at, updated_at=timezone.now()
    )
    where = "credited to your savings" if entry.savings_account_id else "paid to your bank account"
    notifications.notify_member(
        entry.member, category=notifications.Category.DIVIDEND,
        title=f"{cycle.financial_year} dividend paid",
        body=f"Your dividend of {notifications.naira(entry.amount)} has been {where}.",
        link=notifications.link("dividends"),
    )


class DividendPaymentBatchHandler(BatchHandler):
    """Built by prepare_payment(); no file upload."""

    batch_type = BatchType.DIVIDEND_PAYMENTS
    permissions = (P.PAY_DIVIDENDS,)
    accepts_files = False

    def after_post(self, batch):
        cycle = DividendCycle.objects.get(pk=batch.validation_report["dividend_cycle_id"])
        cycle.status = CYCLE.PAID
        cycle.paid_at = batch.posted_at
        cycle.save(update_fields=["status", "paid_at", "updated_at"])
        record("dividend.paid", actor=batch.approved_by, obj=cycle, metadata={"batch": batch.reference})
