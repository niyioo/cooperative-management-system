"""
Posting to the ledger (ARCHITECTURE.md D1, D4, D5).

Every money movement is created by create_entry(). Types listed in
CooperativeSettings.maker_checker_types start PENDING and post only when a
second officer approves them. Batch lines are always PENDING and post together
when the batch is approved. Posted entries are immutable (a DB trigger enforces
this); corrections are reversals (Phase 8).
"""
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.money import to_money
from apps.common.spreadsheets import SpreadsheetError, read_table
from apps.configuration.models import CooperativeSettings

from . import hooks
from .batches import get_handler
from .choices import TYPE_RULES, BatchStatus, EntrySide, TransactionStatus
from .models import Transaction, TransactionBatch
from .selectors import SIGNED_AMOUNT, ZERO

ACCOUNT_FIELDS = {
    "savings.savingsaccount": "savings_account",
    "loans.loan": "loan",
    "investments.investmentaccount": "investment_account",
}
ACCOUNT_FIELDS_BY_KIND = {"SAVINGS": "savings_account", "LOAN": "loan", "INVESTMENT": "investment_account"}


def requires_approval(txn_type):
    return txn_type in CooperativeSettings.load().maker_checker_types


def account_field(account):
    return ACCOUNT_FIELDS[account._meta.label_lower]


def lock_account(account):
    """Serialise postings to one account (row lock until the transaction ends)."""
    return type(account).objects.select_for_update().get(pk=account.pk)


def posted_balance(account):
    field = account_field(account)
    total = Transaction.objects.posted().filter(**{field: account}).aggregate(net=Sum(SIGNED_AMOUNT))["net"]
    return total or ZERO


def pending_debits(account, *, exclude_pk=None):
    field = account_field(account)
    qs = Transaction.objects.pending().filter(**{field: account}, entry_side=EntrySide.DEBIT)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.aggregate(total=Sum("amount"))["total"] or ZERO


def assert_sufficient_balance(account, amount, *, include_pending=True, exclude_pk=None):
    """Money can't leave a savings or investment account that doesn't hold it (BR-20)."""
    available = posted_balance(account)
    if include_pending:
        available -= pending_debits(account, exclude_pk=exclude_pk)
    if amount > available:
        raise DomainError(
            f"Insufficient balance: ₦{available:,.2f} available, ₦{amount:,.2f} requested.",
            code="insufficient_balance",
        )


def create_entry(
    actor,
    *,
    member,
    txn_type,
    amount,
    account=None,
    entry_side=None,
    value_date=None,
    period=None,
    description="",
    external_reference="",
    batch=None,
    closure_request=None,
    reverses=None,
    audit=True,
    require_approval=None,
):
    """
    Create one ledger entry. Callers (module services) check business rules and
    permissions first. Must run inside a transaction.

    require_approval: None = follow CooperativeSettings.maker_checker_types.
    False is for system follow-on entries of an already-approved action (e.g.
    the interest charge that accompanies an approved disbursement).
    """
    kind, fixed_side = TYPE_RULES[txn_type]
    side = fixed_side or entry_side
    if side is None:
        raise ValueError(f"{txn_type} needs an explicit entry_side.")
    amount = to_money(amount)
    if amount <= 0:
        raise DomainError("Amount must be greater than zero.", code="invalid_amount", fields={"amount": ["Must be greater than zero."]})
    value_date = value_date or timezone.localdate()
    if value_date > timezone.localdate():
        raise DomainError("The value date cannot be in the future.", code="future_date", fields={"value_date": ["Cannot be in the future."]})

    accounts = {}
    if account is not None:
        field = account_field(account)
        if kind and ACCOUNT_FIELDS_BY_KIND[kind] != field:
            raise ValueError(f"{txn_type} cannot post to a {field}.")
        accounts[field] = account

    if batch is not None:
        pending = True
    elif require_approval is None:
        pending = requires_approval(txn_type)
    else:
        pending = require_approval
    now = timezone.now()
    entry = Transaction.objects.create(
        member=member,
        txn_type=txn_type,
        entry_side=side,
        amount=amount,
        value_date=value_date,
        period=period,
        description=description,
        external_reference=external_reference,
        batch=batch,
        closure_request=closure_request,
        reverses=reverses,
        status=TransactionStatus.PENDING if pending else TransactionStatus.POSTED,
        posted_at=None if pending else now,
        created_by=actor,
        **accounts,
    )
    if audit:
        record(
            "ledger.entry_created" if pending else "ledger.entry_posted",
            actor=actor,
            obj=entry,
            metadata={"type": txn_type, "amount": amount, "status": entry.status},
        )
    if not pending:
        hooks.run_posted(entry)
    return entry



# ---------------------------------------------------------------------------
# Approving single entries (maker-checker)
# ---------------------------------------------------------------------------

def _account_of(entry):
    return entry.savings_account or entry.loan or entry.investment_account


@transaction.atomic
def approve_entry(actor, entry):
    require_perm(actor, P.APPROVE_TRANSACTION)
    entry = Transaction.objects.select_for_update(of=("self",)).select_related("member").get(pk=entry.pk)
    if entry.batch_id:
        raise DomainError("Entries in a batch are approved with their batch.", code="batch_entry")
    if entry.status != TransactionStatus.PENDING:
        raise DomainError("Only pending entries can be approved.", code="not_pending")
    if entry.created_by_id == actor.pk:
        raise DomainError(
            "You cannot approve an entry you created. Another officer must approve it.", code="maker_checker"
        )
    assert_not_self(actor, entry.member, "approve transactions for")

    account = _account_of(entry)
    if account is not None and entry.entry_side == EntrySide.DEBIT and not entry.loan_id:
        lock_account(account)
        assert_sufficient_balance(account, entry.amount, include_pending=False)

    now = timezone.now()
    entry.status = TransactionStatus.POSTED
    entry.approved_by = actor
    entry.approved_at = now
    entry.posted_at = now
    entry.save(update_fields=["status", "approved_by", "approved_at", "posted_at", "updated_at"])
    record("ledger.entry_approved", actor=actor, obj=entry, metadata={"type": entry.txn_type, "amount": entry.amount})
    hooks.run_posted(entry)
    return entry


@transaction.atomic
def reject_entry(actor, entry, *, reason):
    """The creator may cancel their own pending entry; anyone else needs approve_transaction."""
    entry = Transaction.objects.select_for_update(of=("self",)).select_related("member").get(pk=entry.pk)
    if entry.batch_id:
        raise DomainError("Entries in a batch are rejected with their batch.", code="batch_entry")
    if entry.status != TransactionStatus.PENDING:
        raise DomainError("Only pending entries can be rejected.", code="not_pending")
    if not (reason or "").strip():
        raise DomainError("Please give a reason.", code="reason_required", fields={"reason": ["Please give a reason."]})

    cancelling_own = entry.created_by_id == actor.pk
    if not cancelling_own:
        require_perm(actor, P.APPROVE_TRANSACTION)
        assert_not_self(actor, entry.member, "reject transactions for")
        entry.approved_by = actor
        entry.approved_at = timezone.now()
    entry.status = TransactionStatus.REJECTED
    entry.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record(
        "ledger.entry_cancelled" if cancelling_own else "ledger.entry_rejected",
        actor=actor,
        obj=entry,
        metadata={"reason": reason.strip(), "type": entry.txn_type, "amount": entry.amount},
    )
    hooks.run_rejected(entry)
    return entry


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------

def _empty_report(file_error):
    return {"total_rows": 0, "valid_rows": 0, "error_rows": 0, "errors": [], "unknown_columns": [], "file_errors": [file_error]}


@transaction.atomic
def create_batch_from_file(actor, *, batch_type, file, options, description=""):
    """
    Validate an uploaded batch file. If every row is valid, create its lines as
    PENDING entries (status VALIDATED); otherwise keep the report (status DRAFT)
    and create nothing.
    """
    handler = get_handler(batch_type)
    require_perm(actor, P.MANAGE_BATCHES, *handler.permissions)
    batch = TransactionBatch.objects.create(
        batch_type=batch_type,
        period=options.get("period"),
        description=description,
        source_file=file,
        created_by=actor,
    )
    try:
        header, data = read_table(file, what="entries")
        lines, report = handler.validate_file(header, data, options)
    except SpreadsheetError as exc:
        lines, report = [], _empty_report(str(exc))

    if not report["file_errors"] and not report["errors"]:
        handler.create_lines(actor, batch, lines)
        batch.status = BatchStatus.VALIDATED
    batch.validation_report = report
    _refresh_totals(batch)
    batch.save()
    record(
        "batch.uploaded",
        actor=actor,
        obj=batch,
        metadata={"type": batch_type, "rows": report["total_rows"], "error_rows": report["error_rows"], "file_errors": report["file_errors"]},
    )
    return batch


def create_batch_from_entries(actor, *, batch_type, build_lines, period=None, description=""):
    """For system-built batches (e.g. a cycle payout): build_lines(batch) creates the PENDING entries."""
    batch = TransactionBatch.objects.create(
        batch_type=batch_type, period=period, description=description, created_by=actor, status=BatchStatus.VALIDATED
    )
    build_lines(batch)
    _refresh_totals(batch)
    if batch.line_count == 0:
        raise DomainError("There is nothing to include in this batch.", code="empty_batch")
    batch.save()
    record("batch.created", actor=actor, obj=batch, metadata={"type": batch_type, "lines": batch.line_count})
    return batch


def _refresh_totals(batch):
    agg = batch.transactions.aggregate(total=Sum("amount"))
    batch.line_count = batch.transactions.count()
    batch.total_amount = agg["total"] or ZERO


def _locked(batch):
    return TransactionBatch.objects.select_for_update().get(pk=batch.pk)


@transaction.atomic
def submit_batch(actor, batch):
    require_perm(actor, P.MANAGE_BATCHES)
    batch = _locked(batch)
    if batch.status != BatchStatus.VALIDATED:
        raise DomainError("Only a validated batch can be submitted for approval.", code="invalid_batch_status")
    batch.status = BatchStatus.SUBMITTED
    batch.submitted_at = timezone.now()
    batch.save(update_fields=["status", "submitted_at", "updated_at"])
    record("batch.submitted", actor=actor, obj=batch, metadata={"lines": batch.line_count, "total": batch.total_amount})
    return batch


@transaction.atomic
def approve_batch(actor, batch):
    """Post every line of a submitted batch at once, after re-checking it against current records."""
    require_perm(actor, P.APPROVE_BATCH)
    batch = _locked(batch)
    if batch.status != BatchStatus.SUBMITTED:
        raise DomainError("Only a submitted batch can be approved.", code="invalid_batch_status")
    if batch.created_by_id == actor.pk:
        raise DomainError("You cannot approve a batch you prepared. Another officer must approve it.", code="maker_checker")

    handler = get_handler(batch.batch_type)
    problems = handler.revalidate(batch)
    if problems:
        raise DomainError(
            f"{len(problems)} line(s) no longer pass validation. Reject the batch and upload a corrected one.",
            code="batch_conflicts",
            fields={"lines": problems},
        )

    now = timezone.now()
    posted = batch.transactions.filter(status=TransactionStatus.PENDING).update(
        status=TransactionStatus.POSTED, approved_by=actor, approved_at=now, posted_at=now, updated_at=now
    )
    batch.status = BatchStatus.POSTED
    batch.approved_by = actor
    batch.approved_at = now
    batch.posted_at = now
    batch.save(update_fields=["status", "approved_by", "approved_at", "posted_at", "updated_at"])
    for entry in batch.transactions.filter(status=TransactionStatus.POSTED).order_by("created_at"):
        hooks.run_posted(entry)
    handler.after_post(batch)
    record("batch.posted", actor=actor, obj=batch, metadata={"lines": posted, "total": batch.total_amount})
    return batch


@transaction.atomic
def reject_batch(actor, batch, *, reason):
    """The preparer may discard their own batch; otherwise approve_batch is required."""
    batch = _locked(batch)
    if batch.status in (BatchStatus.POSTED, BatchStatus.REJECTED):
        raise DomainError("This batch is already closed.", code="invalid_batch_status")
    if not (reason or "").strip():
        raise DomainError("Please give a reason.", code="reason_required", fields={"reason": ["Please give a reason."]})
    discarding_own = batch.created_by_id == actor.pk
    if not discarding_own:
        require_perm(actor, P.APPROVE_BATCH)

    now = timezone.now()
    lines = batch.transactions.filter(status=TransactionStatus.PENDING)
    if discarding_own:
        lines.update(status=TransactionStatus.REJECTED, updated_at=now)
    else:
        lines.update(status=TransactionStatus.REJECTED, approved_by=actor, approved_at=now, updated_at=now)
    batch.status = BatchStatus.REJECTED
    batch.rejection_reason = reason.strip()
    batch.save(update_fields=["status", "rejection_reason", "updated_at"])
    for entry in batch.transactions.filter(status=TransactionStatus.REJECTED):
        hooks.run_rejected(entry)
    get_handler(batch.batch_type).after_reject(batch)
    record(
        "batch.discarded" if discarding_own else "batch.rejected",
        actor=actor,
        obj=batch,
        metadata={"reason": reason.strip()},
    )
    return batch
