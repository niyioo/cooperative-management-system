"""
The central ledger: the single source of truth for money (ARCHITECTURE.md D1).

Every financial event is one Transaction row. Balances are derived by summing
POSTED rows. Posted rows are never edited or deleted; corrections are REVERSAL
entries. A PostgreSQL trigger (migration 0002) enforces this at the database.
"""
from functools import reduce
from operator import or_

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.common.fields import MoneyField
from apps.common.models import ReferenceMixin, TimeStampedModel
from apps.common.uploads import batch_source_path
from apps.common.validators import spreadsheet_extension_validator, validate_file_signature, validate_file_size

from .choices import (
    INVESTMENT_TYPES,
    LOAN_TYPES,
    SAVINGS_TYPES,
    TYPE_RULES,
    BatchStatus,
    BatchType,
    EntrySide,
    TransactionStatus,
    TransactionType,
)


def _fixed_side_condition():
    """Types with a fixed side (e.g. contributions are always CREDIT) must use it."""
    free = [t for t, (_, side) in TYPE_RULES.items() if side is None]
    clauses = [Q(txn_type__in=free)]
    for side in EntrySide.values:
        types = [t for t, (_, s) in TYPE_RULES.items() if s == side]
        clauses.append(Q(txn_type__in=types, entry_side=side))
    return reduce(or_, clauses)


class TransactionBatch(ReferenceMixin, TimeStampedModel):
    """
    A bulk posting, typically a monthly payroll deduction schedule. Lines are
    created as PENDING transactions and all post together once a second officer
    approves the batch.
    """

    REFERENCE_PREFIX = "BAT"

    reference = models.CharField(max_length=30, unique=True, editable=False)
    batch_type = models.CharField(max_length=30, choices=BatchType.choices)
    period = models.DateField(
        null=True, blank=True, help_text="First day of the month the batch relates to."
    )
    description = models.CharField(max_length=255, blank=True)
    source_file = models.FileField(
        upload_to=batch_source_path,
        blank=True,
        validators=[spreadsheet_extension_validator, validate_file_size, validate_file_signature],
    )
    line_count = models.PositiveIntegerField(default=0)
    total_amount = MoneyField(default=0)
    status = models.CharField(
        max_length=20, choices=BatchStatus.choices, default=BatchStatus.DRAFT
    )
    validation_report = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        verbose_name_plural = "transaction batches"
        constraints = [
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True) | ~Q(approved_by=F("created_by")),
                name="ledger_batch_maker_checker",
            ),
            models.CheckConstraint(
                condition=Q(period__isnull=True) | Q(period__day=1),
                name="ledger_batch_period_first_of_month",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0), name="ledger_batch_total_non_negative"
            ),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_batch_type_display()})"


class TransactionQuerySet(models.QuerySet):
    def posted(self):
        """Entries that count toward balances. A reversed entry and its reversal both count and cancel out."""
        return self.filter(status__in=[TransactionStatus.POSTED, TransactionStatus.REVERSED])

    def pending(self):
        return self.filter(status=TransactionStatus.PENDING)

    def for_member(self, member):
        return self.filter(member=member)


class Transaction(ReferenceMixin, TimeStampedModel):
    REFERENCE_PREFIX = "TXN"
    REFERENCE_WIDTH = 6

    reference = models.CharField(max_length=30, unique=True, editable=False)
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="transactions"
    )
    txn_type = models.CharField(max_length=40, choices=TransactionType.choices)
    entry_side = models.CharField(max_length=6, choices=EntrySide.choices)
    amount = MoneyField()
    value_date = models.DateField(default=timezone.localdate)
    period = models.DateField(
        null=True,
        blank=True,
        help_text="First day of the month this entry counts for (contributions, repayments).",
    )

    # Exactly one account is set (except an externally paid dividend, which has none).
    savings_account = models.ForeignKey(
        "savings.SavingsAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.PROTECT, null=True, blank=True, related_name="transactions"
    )
    investment_account = models.ForeignKey(
        "investments.InvestmentAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )

    batch = models.ForeignKey(
        TransactionBatch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    closure_request = models.ForeignKey(
        "closures.AccountClosureRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="settlement_transactions",
    )
    description = models.CharField(max_length=255, blank=True)
    external_reference = models.CharField(
        max_length=100, blank=True, help_text="Payroll run, bank teller or receipt number."
    )

    status = models.CharField(
        max_length=10, choices=TransactionStatus.choices, default=TransactionStatus.PENDING
    )
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
        help_text="The entry this REVERSAL cancels. An entry can be reversed only once.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Null only for system-generated entries.",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)

    objects = TransactionQuerySet.as_manager()

    class Meta(TimeStampedModel.Meta):
        ordering = ["-value_date", "-created_at"]
        permissions = [
            ("view_all_transactions", "View all members' transactions"),
            ("approve_transaction", "Approve or reject pending transactions"),
            ("reverse_transaction", "Reverse posted transactions"),
            ("post_adjustment", "Create adjustment entries"),
            ("manage_batches", "Upload and submit transaction batches"),
            ("approve_batch", "Approve transaction batches"),
        ]
        indexes = [
            models.Index(fields=["member", "value_date"], name="ledger_txn_member_date"),
            models.Index(fields=["savings_account", "status"], name="ledger_txn_savings_status"),
            models.Index(fields=["loan", "status"], name="ledger_txn_loan_status"),
            models.Index(
                fields=["investment_account", "status"], name="ledger_txn_invest_status"
            ),
            models.Index(fields=["txn_type", "value_date"], name="ledger_txn_type_date"),
            models.Index(fields=["status", "created_at"], name="ledger_txn_status_created"),
            models.Index(fields=["period"], name="ledger_txn_period"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_txn_amount_positive"),
            models.CheckConstraint(
                condition=(
                    Q(savings_account__isnull=False, loan__isnull=True, investment_account__isnull=True)
                    | Q(savings_account__isnull=True, loan__isnull=False, investment_account__isnull=True)
                    | Q(savings_account__isnull=True, loan__isnull=True, investment_account__isnull=False)
                    | Q(
                        savings_account__isnull=True,
                        loan__isnull=True,
                        investment_account__isnull=True,
                        txn_type=TransactionType.DIVIDEND_PAYMENT,
                    )
                ),
                name="ledger_txn_exactly_one_account",
            ),
            models.CheckConstraint(
                condition=(
                    Q(txn_type__in=SAVINGS_TYPES, savings_account__isnull=False)
                    | Q(txn_type__in=LOAN_TYPES, loan__isnull=False)
                    | Q(txn_type__in=INVESTMENT_TYPES, investment_account__isnull=False)
                    | Q(txn_type=TransactionType.DIVIDEND_PAYMENT, loan__isnull=True, investment_account__isnull=True)
                    | Q(txn_type__in=[TransactionType.ADJUSTMENT, TransactionType.REVERSAL])
                ),
                name="ledger_txn_type_matches_account",
            ),
            models.CheckConstraint(condition=_fixed_side_condition(), name="ledger_txn_type_side"),
            models.CheckConstraint(
                condition=Q(period__isnull=True) | Q(period__day=1),
                name="ledger_txn_period_first_of_month",
            ),
            models.CheckConstraint(
                condition=(
                    Q(txn_type=TransactionType.REVERSAL, reverses__isnull=False)
                    | (~Q(txn_type=TransactionType.REVERSAL) & Q(reverses__isnull=True))
                ),
                name="ledger_txn_reversal_link",
            ),
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True) | ~Q(approved_by=F("created_by")),
                name="ledger_txn_maker_checker",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status__in=[TransactionStatus.POSTED, TransactionStatus.REVERSED], posted_at__isnull=False)
                    | Q(status__in=[TransactionStatus.PENDING, TransactionStatus.REJECTED], posted_at__isnull=True)
                ),
                name="ledger_txn_posted_at_matches_status",
            ),
        ]

    def __str__(self):
        return f"{self.reference} {self.get_txn_type_display()} ₦{self.amount:,.2f} ({self.status})"

    @property
    def signed_amount(self):
        """+amount for credits, -amount for debits."""
        return self.amount if self.entry_side == EntrySide.CREDIT else -self.amount
