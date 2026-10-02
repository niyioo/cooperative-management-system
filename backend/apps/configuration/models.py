from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.uploads import cooperative_logo_path
from apps.common.validators import MONTH_VALIDATORS, image_extension_validator
from apps.ledger.choices import DEFAULT_MAKER_CHECKER_TYPES, TransactionType


def default_maker_checker_types():
    return list(DEFAULT_MAKER_CHECKER_TYPES)


class CooperativeSettings(models.Model):
    """
    Cooperative-wide configuration. Exactly one row (id=1), read with
    CooperativeSettings.load().
    """

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    # Identity
    name = models.CharField(max_length=200, default="EMDI Cooperative Society")
    short_name = models.CharField(max_length=50, default="EMDI Coop")
    parent_institution = models.CharField(
        max_length=255,
        default="Engineering Materials Development Institute (EMDI), NASENI",
    )
    registration_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    logo = models.ImageField(
        upload_to=cooperative_logo_path, blank=True, validators=[image_extension_validator]
    )

    # Formats and calendar
    currency_code = models.CharField(max_length=3, default="NGN")
    membership_number_format = models.CharField(
        max_length=50,
        default="EMDI/COOP/{seq:04d}",
        help_text="Python format string; {seq} is the next number, {year} the current year.",
    )
    financial_year_start_month = models.PositiveSmallIntegerField(
        default=1, validators=MONTH_VALIDATORS
    )
    dividend_processing_month = models.PositiveSmallIntegerField(
        default=12, validators=MONTH_VALIDATORS
    )

    # Rules
    member_withdrawal_requests_enabled = models.BooleanField(
        default=False,
        help_text="Global switch. While off, no savings product can accept member withdrawal requests.",
    )
    closure_disables_portal_login = models.BooleanField(default=True)
    maker_checker_types = ArrayField(
        models.CharField(max_length=40, choices=TransactionType.choices),
        default=default_maker_checker_types,
        blank=True,
        help_text="Transaction types that must be approved by a second officer before posting.",
    )
    loan_overdue_grace_days = models.PositiveSmallIntegerField(default=7)

    # Security
    session_idle_timeout_minutes = models.PositiveSmallIntegerField(default=30)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        permissions = [("manage_settings", "Manage cooperative settings")]
        verbose_name = "cooperative settings"
        verbose_name_plural = "cooperative settings"
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="cooperative_settings_singleton"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Department(TimeStampedModel):
    """EMDI departments/units, used on member employment records."""

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper() if self.code else None
        super().save(*args, **kwargs)
