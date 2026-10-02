"""
Configurable savings products (ARCHITECTURE.md D2/D3).

Christmas Savings is a CYCLE product (January → October). Each year is a
SavingsCycle, and each member has one SavingsAccount per cycle. Regular savings
are REGULAR products with one continuous account per member. Balances are
never stored; they are derived from the ledger.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.common.fields import MoneyField
from apps.common.models import TimeStampedModel
from apps.common.validators import MONTH_VALIDATORS
from apps.ledger.models import Transaction, TransactionQuerySet


class ProductKind(models.TextChoices):
    REGULAR = "REGULAR", "Regular (continuous)"
    CYCLE = "CYCLE", "Cycle (yearly contribution window)"


class SavingsProduct(TimeStampedModel):
    Kind = ProductKind

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code, e.g. CHRISTMAS or REGULAR.")
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=ProductKind.choices)

    # Cycle window (CYCLE products only). Cycles run within one calendar year.
    cycle_start_month = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=MONTH_VALIDATORS
    )
    cycle_end_month = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=MONTH_VALIDATORS
    )
    payout_month = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=MONTH_VALIDATORS
    )

    # Contribution rules
    expected_monthly_contribution = MoneyField(default=0)
    min_contribution = MoneyField(default=0)
    allow_contribution_outside_window = models.BooleanField(default=False)
    allow_multiple_contributions_per_period = models.BooleanField(default=False)

    # Eligibility
    min_membership_months = models.PositiveSmallIntegerField(default=0)
    is_mandatory = models.BooleanField(
        default=False, help_text="Opened automatically for every new member."
    )

    # Withdrawals. EMDI: members cannot withdraw savings (BR-01).
    allow_officer_withdrawal = models.BooleanField(default=False)
    allow_member_withdrawal_request = models.BooleanField(
        default=False,
        help_text="Also requires the global setting. Off for EMDI.",
    )

    counts_toward_loan_eligibility = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        ordering = ["display_order", "name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind=ProductKind.CYCLE, cycle_start_month__isnull=False, cycle_end_month__isnull=False)
                    | Q(
                        kind=ProductKind.REGULAR,
                        cycle_start_month__isnull=True,
                        cycle_end_month__isnull=True,
                        payout_month__isnull=True,
                    )
                ),
                name="savings_product_cycle_window_matches_kind",
            ),
            models.CheckConstraint(
                condition=Q(cycle_start_month__isnull=True) | Q(cycle_start_month__lte=F("cycle_end_month")),
                name="savings_product_cycle_start_before_end",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(cycle_start_month__isnull=True) | Q(cycle_start_month__range=(1, 12)))
                    & (Q(cycle_end_month__isnull=True) | Q(cycle_end_month__range=(1, 12)))
                    & (Q(payout_month__isnull=True) | Q(payout_month__range=(1, 12)))
                ),
                name="savings_product_months_valid",
            ),
            models.CheckConstraint(
                condition=Q(expected_monthly_contribution__gte=0) & Q(min_contribution__gte=0),
                name="savings_product_amounts_non_negative",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_cycle(self):
        return self.kind == ProductKind.CYCLE


class SavingsCycle(TimeStampedModel):
    """One yearly run of a cycle product, e.g. Christmas Savings 2026 (the spec's ChristmasSavings)."""

    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "Upcoming"
        OPEN = "OPEN", "Open for contributions"
        CLOSED = "CLOSED", "Closed"
        PAID_OUT = "PAID_OUT", "Paid out"

    product = models.ForeignKey(
        SavingsProduct,
        on_delete=models.PROTECT,
        related_name="cycles",
        limit_choices_to={"kind": ProductKind.CYCLE},
    )
    year = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    expected_monthly_contribution = MoneyField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UPCOMING)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-year", "product__display_order"]
        constraints = [
            models.UniqueConstraint(fields=["product", "year"], name="savings_cycle_unique_product_year"),
            models.CheckConstraint(condition=Q(start_date__lte=F("end_date")), name="savings_cycle_dates_ordered"),
            models.CheckConstraint(
                condition=Q(expected_monthly_contribution__gte=0),
                name="savings_cycle_expected_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} {self.year}"


class SavingsAccount(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FROZEN = "FROZEN", "Frozen"
        CLOSED = "CLOSED", "Closed"

    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="savings_accounts"
    )
    product = models.ForeignKey(SavingsProduct, on_delete=models.PROTECT, related_name="accounts")
    cycle = models.ForeignKey(
        SavingsCycle,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="accounts",
        help_text="Set for cycle products only (validated in the service layer).",
    )
    account_number = models.CharField(max_length=20, unique=True, blank=True)
    elected_monthly_amount = MoneyField(
        null=True, blank=True, help_text="Member's chosen monthly amount; blank uses the product/cycle default."
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    opened_on = models.DateField(default=timezone.localdate)
    closed_on = models.DateField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["product__display_order", "-opened_on"]
        permissions = [
            ("view_savings", "View savings"),
            ("manage_savings_products", "Configure savings products"),
            ("manage_savings_cycles", "Create and open savings cycles"),
            ("close_savings_cycle", "Close savings cycles"),
            ("post_savings_contribution", "Post savings contributions"),
            ("post_savings_withdrawal", "Post savings withdrawals and cycle payouts"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "product"],
                condition=Q(cycle__isnull=True),
                name="savings_account_one_regular_per_member_product",
            ),
            models.UniqueConstraint(
                fields=["member", "cycle"],
                condition=Q(cycle__isnull=False),
                name="savings_account_one_per_member_cycle",
            ),
            models.CheckConstraint(
                condition=Q(elected_monthly_amount__isnull=True) | Q(elected_monthly_amount__gte=0),
                name="savings_account_elected_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="CLOSED", closed_on__isnull=False)
                    | (~Q(status="CLOSED") & Q(closed_on__isnull=True))
                ),
                name="savings_account_closed_on_matches_status",
            ),
        ]

    def __str__(self):
        label = str(self.cycle) if self.cycle_id else self.product.name
        return f"{self.account_number} — {label}"

    def save(self, *args, **kwargs):
        if not self.account_number:
            from apps.common.sequences import next_value

            self.account_number = f"SV{next_value('SAVINGS_ACCOUNT'):08d}"
        super().save(*args, **kwargs)


class SavingsTransactionManager(models.Manager.from_queryset(TransactionQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(savings_account__isnull=False)


class SavingsTransaction(Transaction):
    """Ledger entries on savings accounts. A proxy, so the amount lives only in the ledger."""

    objects = SavingsTransactionManager()

    class Meta:
        proxy = True
        default_permissions = ()
        ordering = ["-value_date", "-created_at"]
