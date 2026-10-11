"""
Annual dividend cycles (processed in December).

Every calculation is a new DividendCalculationRun; recalculating supersedes the
previous run but keeps it, so no calculated figure is ever silently changed.
Approving a cycle locks one run. Members see results only once the cycle is
PUBLISHED.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.fields import MoneyField, RateField
from apps.common.models import ReferenceMixin, TimeStampedModel


class DividendCycle(ReferenceMixin, TimeStampedModel):
    REFERENCE_PREFIX = "DIV"
    REFERENCE_WIDTH = 2

    class Basis(models.TextChoices):
        CLOSING_BALANCE = "CLOSING_BALANCE", "Balance at cutoff date"
        AVERAGE_MONTHLY_BALANCE = "AVERAGE_MONTHLY_BALANCE", "Average month-end balance"
        MINIMUM_BALANCE = "MINIMUM_BALANCE", "Lowest month-end balance"

    class PaymentMethod(models.TextChoices):
        CREDIT_TO_SAVINGS = "CREDIT_TO_SAVINGS", "Credit to savings account"
        EXTERNAL = "EXTERNAL", "Paid externally (bank/cash)"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CALCULATED = "CALCULATED", "Calculated"
        APPROVED = "APPROVED", "Approved"
        PUBLISHED = "PUBLISHED", "Published to members"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    reference = models.CharField(max_length=30, unique=True, editable=False)
    financial_year = models.PositiveSmallIntegerField()
    eligible_investment_products = models.ManyToManyField(
        "investments.InvestmentProduct", blank=True, related_name="dividend_cycles"
    )
    eligible_savings_products = models.ManyToManyField(
        "savings.SavingsProduct", blank=True, related_name="dividend_cycles"
    )
    basis = models.CharField(max_length=25, choices=Basis.choices, default=Basis.AVERAGE_MONTHLY_BALANCE)
    cutoff_date = models.DateField()
    rate = RateField(help_text="Dividend rate as a percentage.")
    distributable_surplus = MoneyField(
        null=True, blank=True, help_text="Optional ceiling: total gross dividends must not exceed it."
    )
    withholding_rate = RateField(default=0)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CREDIT_TO_SAVINGS
    )
    credit_savings_product = models.ForeignKey(
        "savings.SavingsProduct",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Savings product credited when paying by CREDIT_TO_SAVINGS.",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    approved_run = models.OneToOneField(
        "DividendCalculationRun", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-financial_year"]
        permissions = [
            ("view_dividends", "View dividend cycles"),
            ("manage_dividend_cycles", "Create and configure dividend cycles"),
            ("calculate_dividends", "Run dividend calculations"),
            ("approve_dividends", "Approve and publish dividend cycles"),
            ("pay_dividends", "Pay approved dividends"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["financial_year"],
                condition=~Q(status="CANCELLED"),
                name="dividend_cycle_one_live_per_year",
            ),
            models.CheckConstraint(condition=Q(rate__gte=0), name="dividend_cycle_rate_non_negative"),
            models.CheckConstraint(
                condition=Q(withholding_rate__gte=0) & Q(withholding_rate__lte=100),
                name="dividend_cycle_withholding_range",
            ),
            models.CheckConstraint(
                condition=~Q(payment_method="CREDIT_TO_SAVINGS") | Q(credit_savings_product__isnull=False),
                name="dividend_cycle_credit_product_required",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["APPROVED", "PUBLISHED", "PAID"])
                | Q(approved_run__isnull=False, approved_by__isnull=False),
                name="dividend_cycle_approval_recorded",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.financial_year} dividend"

    def build_reference(self):
        from apps.common.sequences import generate_reference

        return generate_reference(self.REFERENCE_PREFIX, width=self.REFERENCE_WIDTH, year=self.financial_year)


class DividendCalculationRun(TimeStampedModel):
    """One calculation of a cycle. created_at is the run time; parameters snapshot the inputs."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Awaiting approval"
        SUPERSEDED = "SUPERSEDED", "Superseded by a later run"
        APPROVED = "APPROVED", "Approved"

    cycle = models.ForeignKey(DividendCycle, on_delete=models.PROTECT, related_name="runs")
    run_number = models.PositiveSmallIntegerField()
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    parameters = models.JSONField(default=dict)
    total_basis = MoneyField(default=0)
    total_gross = MoneyField(default=0)
    total_withholding = MoneyField(default=0)
    total_net = MoneyField(default=0)
    member_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    class Meta(TimeStampedModel.Meta):
        ordering = ["cycle", "-run_number"]
        constraints = [
            models.UniqueConstraint(fields=["cycle", "run_number"], name="dividend_run_unique_number"),
            models.UniqueConstraint(
                fields=["cycle"], condition=Q(status="APPROVED"), name="dividend_run_one_approved_per_cycle"
            ),
            models.CheckConstraint(
                condition=Q(total_net=F("total_gross") - F("total_withholding")),
                name="dividend_run_net_equals_gross_less_withholding",
            ),
        ]

    def __str__(self):
        return f"{self.cycle.reference} run {self.run_number}"


class MemberDividend(TimeStampedModel):
    class Status(models.TextChoices):
        CALCULATED = "CALCULATED", "Calculated"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        WITHHELD = "WITHHELD", "Withheld"

    run = models.ForeignKey(DividendCalculationRun, on_delete=models.PROTECT, related_name="member_dividends")
    cycle = models.ForeignKey(DividendCycle, on_delete=models.PROTECT, related_name="member_dividends")
    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="dividends")
    basis_amount = MoneyField()
    rate = RateField()
    gross_amount = MoneyField()
    withholding_amount = MoneyField(default=0)
    net_amount = MoneyField()
    calculation_detail = models.JSONField(
        default=dict, help_text="Inputs used, e.g. the month-end balances behind an average."
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CALCULATED)
    payment_transaction = models.OneToOneField(
        "ledger.Transaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="member_dividend",
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["member__last_name", "member__first_name"]
        indexes = [models.Index(fields=["member", "cycle"], name="dividends_member_cycle")]
        constraints = [
            models.UniqueConstraint(fields=["run", "member"], name="member_dividend_unique_per_run"),
            models.CheckConstraint(
                condition=Q(basis_amount__gte=0) & Q(gross_amount__gte=0) & Q(withholding_amount__gte=0),
                name="member_dividend_amounts_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(net_amount=F("gross_amount") - F("withholding_amount")),
                name="member_dividend_net_equals_gross_less_withholding",
            ),
            models.CheckConstraint(
                condition=~Q(status="PAID") | Q(payment_transaction__isnull=False, paid_at__isnull=False),
                name="member_dividend_paid_has_transaction",
            ),
        ]

    def __str__(self):
        return f"{self.member} {self.cycle.financial_year}: ₦{self.net_amount:,.2f}"
