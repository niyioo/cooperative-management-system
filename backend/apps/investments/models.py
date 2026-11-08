from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.fields import MoneyField
from apps.common.models import TimeStampedModel
from apps.ledger.models import Transaction, TransactionQuerySet


class InvestmentProduct(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    min_amount = MoneyField(default=0)
    lock_in_months = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Months before liquidation is allowed. Blank = none."
    )
    dividend_eligible = models.BooleanField(default=True)
    allow_officer_liquidation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(min_amount__gte=0), name="investment_product_min_non_negative"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class InvestmentAccount(TimeStampedModel):
    """A member's position in an investment scheme. Principal is derived from the ledger."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        MATURED = "MATURED", "Matured"
        LIQUIDATED = "LIQUIDATED", "Liquidated"
        CLOSED = "CLOSED", "Closed"

    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="investment_accounts"
    )
    product = models.ForeignKey(InvestmentProduct, on_delete=models.PROTECT, related_name="accounts")
    account_number = models.CharField(max_length=20, unique=True, blank=True)
    opened_on = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    closed_on = models.DateField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-opened_on"]
        permissions = [
            ("view_investments", "View investments"),
            ("manage_investment_products", "Configure investment products"),
            ("manage_investment_accounts", "Open and close investment accounts"),
            ("post_investment_transaction", "Post investment contributions, liquidations and returns"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["member", "product"],
                condition=Q(status="ACTIVE"),
                name="investment_account_one_active_per_product",
            ),
        ]

    def __str__(self):
        return f"{self.account_number} — {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.account_number:
            from apps.common.sequences import next_value

            self.account_number = f"IV{next_value('INVESTMENT_ACCOUNT'):08d}"
        super().save(*args, **kwargs)


class InvestmentReturn(TimeStampedModel):
    """Returns earned by a scheme at cooperative level. Reporting only; does not move member balances."""

    product = models.ForeignKey(InvestmentProduct, on_delete=models.PROTECT, related_name="returns")
    financial_year = models.PositiveSmallIntegerField()
    amount_earned = MoneyField()
    description = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta(TimeStampedModel.Meta):
        ordering = ["-financial_year", "product__name"]
        indexes = [models.Index(fields=["financial_year"], name="investments_return_year")]

    def __str__(self):
        return f"{self.product.name} {self.financial_year}: ₦{self.amount_earned:,.2f}"


class InvestmentTransactionManager(models.Manager.from_queryset(TransactionQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(investment_account__isnull=False)


class InvestmentTransaction(Transaction):
    """Ledger entries on investment accounts. A proxy, so the amount lives only in the ledger."""

    objects = InvestmentTransactionManager()

    class Meta:
        proxy = True
        default_permissions = ()
        ordering = ["-value_date", "-created_at"]
