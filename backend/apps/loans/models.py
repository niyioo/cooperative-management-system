"""
Loan products, the application workflow and disbursed loans.

A LoanApplication moves through DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED →
DISBURSED (ARCHITECTURE.md §6.2). Disbursement creates a Loan that snapshots
the product terms. The outstanding balance is derived from the ledger:
debits (disbursement, interest, penalties) minus credits (repayments).
"""
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, Q

from apps.common.fields import MoneyField, RateField
from apps.common.models import ReferenceMixin, TimeStampedModel
from apps.common.uploads import loan_document_path
from apps.common.validators import document_extension_validator, validate_file_signature, validate_file_size


class InterestRateBasis(models.TextChoices):
    PER_ANNUM = "PER_ANNUM", "Per annum"
    PER_LOAN = "PER_LOAN", "Flat for the whole term"
    PER_MONTH = "PER_MONTH", "Per month"


class InterestMethod(models.TextChoices):
    FLAT = "FLAT", "Flat"
    REDUCING_BALANCE = "REDUCING_BALANCE", "Reducing balance"


class InterestCollection(models.TextChoices):
    AMORTISED = "AMORTISED", "Repaid with instalments"
    UPFRONT = "UPFRONT", "Deducted at disbursement"


class LoanProduct(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    interest_rate = RateField(help_text="Percentage, e.g. 10.0000 for 10%.")
    interest_rate_basis = models.CharField(
        max_length=10, choices=InterestRateBasis.choices, default=InterestRateBasis.PER_ANNUM
    )
    interest_method = models.CharField(
        max_length=20, choices=InterestMethod.choices, default=InterestMethod.FLAT
    )
    interest_collection = models.CharField(
        max_length=10, choices=InterestCollection.choices, default=InterestCollection.AMORTISED
    )

    min_amount = MoneyField(default=0)
    max_amount = MoneyField()
    max_savings_multiple = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Loan may not exceed this multiple of the member's eligible savings. Blank = no rule.",
    )
    min_term_months = models.PositiveSmallIntegerField(default=1)
    max_term_months = models.PositiveSmallIntegerField()
    allowed_terms = ArrayField(
        models.PositiveSmallIntegerField(),
        default=list,
        blank=True,
        help_text="Specific terms offered (months). Empty = any term within the range.",
    )
    min_membership_months = models.PositiveSmallIntegerField(default=0)
    max_active_loans = models.PositiveSmallIntegerField(
        default=1, help_text="Active loans of this product a member may hold at once."
    )
    guarantors_required = models.PositiveSmallIntegerField(
        default=1, help_text="Guarantors (fellow members) each application needs. At least one (BR-28)."
    )
    required_documents = ArrayField(
        models.CharField(max_length=150), default=list, blank=True
    )
    allow_topup = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(interest_rate__gte=0), name="loan_product_rate_non_negative"),
            models.CheckConstraint(
                condition=Q(min_amount__gte=0) & Q(max_amount__gt=0) & Q(min_amount__lte=F("max_amount")),
                name="loan_product_amount_range",
            ),
            models.CheckConstraint(
                condition=Q(min_term_months__gte=1) & Q(min_term_months__lte=F("max_term_months")),
                name="loan_product_term_range",
            ),
            models.CheckConstraint(
                condition=Q(max_savings_multiple__isnull=True) | Q(max_savings_multiple__gt=0),
                name="loan_product_savings_multiple_positive",
            ),
            models.CheckConstraint(condition=Q(guarantors_required__gte=1), name="loan_product_needs_a_guarantor"),
            # "Flat for the whole term" has no meaning for a reducing-balance schedule.
            models.CheckConstraint(
                condition=~Q(interest_method="REDUCING_BALANCE", interest_rate_basis="PER_LOAN"),
                name="loan_product_reducing_needs_periodic_rate",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.interest_rate.normalize()}%)"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class LoanApplication(ReferenceMixin, TimeStampedModel):
    REFERENCE_PREFIX = "LA"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        RETURNED = "RETURNED", "Returned for more information"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        DISBURSED = "DISBURSED", "Disbursed"

    OPEN_STATUSES = [Status.DRAFT, Status.SUBMITTED, Status.UNDER_REVIEW, Status.RETURNED, Status.APPROVED]

    reference = models.CharField(max_length=30, unique=True, editable=False)
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="loan_applications"
    )
    product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT, related_name="applications")
    amount_requested = MoneyField()
    term_months = models.PositiveSmallIntegerField()
    purpose = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)

    eligibility_snapshot = models.JSONField(
        default=dict, blank=True, help_text="Eligibility check results recorded at submission."
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Internal; never shown to the member.")
    info_request_message = models.TextField(blank=True, help_text="Shown to the member when returned.")

    approved_amount = MoneyField(null=True, blank=True)
    approved_term_months = models.PositiveSmallIntegerField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True, help_text="Shown to the member.")
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["member", "status"], name="loans_application_member"),
            models.Index(fields=["status", "submitted_at"], name="loans_application_queue"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount_requested__gt=0), name="loan_application_amount_positive"),
            models.CheckConstraint(condition=Q(term_months__gte=1), name="loan_application_term_positive"),
            models.CheckConstraint(
                condition=(
                    ~Q(status__in=["APPROVED", "DISBURSED"])
                    | Q(approved_amount__gt=0, approved_term_months__gte=1, decided_by__isnull=False)
                ),
                name="loan_application_approval_recorded",
            ),
            models.CheckConstraint(
                condition=Q(status="DRAFT") | Q(submitted_at__isnull=False) | Q(status="CANCELLED"),
                name="loan_application_submitted_at_set",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.member} ({self.get_status_display()})"


class LoanApplicationDocument(TimeStampedModel):
    application = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=150)
    file = models.FileField(
        upload_to=loan_document_path,
        validators=[document_extension_validator, validate_file_size, validate_file_signature],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta(TimeStampedModel.Meta):
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.title} ({self.application.reference})"


class LoanGuarantor(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting response"
        ACCEPTED = "ACCEPTED", "Accepted"
        DECLINED = "DECLINED", "Declined"

    application = models.ForeignKey(LoanApplication, on_delete=models.PROTECT, related_name="guarantors")
    guarantor = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="guarantees"
    )
    amount_guaranteed = MoneyField(help_text="This guarantor's share of the amount requested.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(
        null=True, blank=True, help_text="When the guarantor was asked (notified); empty while the application is a draft."
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    decline_reason = models.CharField(max_length=500, blank=True)

    class Meta(TimeStampedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["application", "guarantor"], name="loan_guarantor_unique"),
            models.CheckConstraint(condition=Q(amount_guaranteed__gt=0), name="loan_guarantor_amount_positive"),
        ]

    def __str__(self):
        return f"{self.guarantor} guarantees {self.application.reference}"


class Loan(ReferenceMixin, TimeStampedModel):
    REFERENCE_PREFIX = "LN"

    class Status(models.TextChoices):
        PENDING_DISBURSEMENT = "PENDING_DISBURSEMENT", "Disbursement awaiting approval"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        DEFAULTED = "DEFAULTED", "Defaulted"
        WRITTEN_OFF = "WRITTEN_OFF", "Written off"
        CANCELLED = "CANCELLED", "Cancelled (disbursement rejected)"

    RUNNING_STATUSES = [Status.ACTIVE, Status.DEFAULTED]

    reference = models.CharField(max_length=30, unique=True, editable=False)
    # A foreign key (not one-to-one) so a rejected disbursement can be retried;
    # a partial unique constraint keeps one live loan per application.
    application = models.ForeignKey(
        LoanApplication,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loans",
        help_text="Blank only for loans migrated from the previous records at go-live.",
    )
    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="loans")
    product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT, related_name="loans")

    principal = MoneyField()
    # Terms snapshotted at approval; later product changes never affect this loan (D6).
    interest_rate = RateField()
    interest_rate_basis = models.CharField(max_length=10, choices=InterestRateBasis.choices)
    interest_method = models.CharField(max_length=20, choices=InterestMethod.choices)
    interest_collection = models.CharField(max_length=10, choices=InterestCollection.choices)
    term_months = models.PositiveSmallIntegerField()
    total_interest = MoneyField(default=0)

    disbursed_on = models.DateField()
    first_due_date = models.DateField()
    maturity_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_DISBURSEMENT)
    completed_on = models.DateField(null=True, blank=True)
    defaulted_on = models.DateField(null=True, blank=True)
    is_migrated = models.BooleanField(default=False)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-disbursed_on", "-created_at"]
        permissions = [
            ("view_loans", "View loans and applications"),
            ("manage_loan_products", "Configure loan products"),
            ("review_loan_application", "Review loan applications"),
            ("approve_loan_application", "Approve or reject loan applications"),
            ("disburse_loan", "Disburse approved loans"),
            ("record_loan_repayment", "Record loan repayments"),
            ("mark_loan_default", "Mark loans as defaulted"),
        ]
        indexes = [
            models.Index(fields=["member", "status"], name="loans_loan_member_status"),
            models.Index(fields=["status", "maturity_date"], name="loans_loan_status_maturity"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loan_principal_positive"),
            models.CheckConstraint(condition=Q(interest_rate__gte=0), name="loan_rate_non_negative"),
            models.CheckConstraint(condition=Q(total_interest__gte=0), name="loan_interest_non_negative"),
            models.CheckConstraint(condition=Q(term_months__gte=1), name="loan_term_positive"),
            models.CheckConstraint(
                condition=Q(first_due_date__gte=F("disbursed_on")) & Q(maturity_date__gte=F("first_due_date")),
                name="loan_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(application__isnull=False) | Q(is_migrated=True),
                name="loan_has_application_unless_migrated",
            ),
            models.UniqueConstraint(
                fields=["application"],
                condition=~Q(status="CANCELLED"),
                name="loan_one_live_loan_per_application",
            ),
            models.CheckConstraint(
                condition=~Q(status="COMPLETED") | Q(completed_on__isnull=False),
                name="loan_completed_on_set",
            ),
            models.CheckConstraint(
                condition=~Q(status="DEFAULTED") | Q(defaulted_on__isnull=False),
                name="loan_defaulted_on_set",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.member} ₦{self.principal:,.2f}"


class RepaymentInstallment(TimeStampedModel):
    """Scheduled instalment, generated at disbursement and never edited. Paid status is derived from allocations."""

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="installments")
    number = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    principal_due = MoneyField()
    interest_due = MoneyField(default=0)

    class Meta(TimeStampedModel.Meta):
        ordering = ["loan", "number"]
        indexes = [models.Index(fields=["due_date"], name="loans_installment_due")]
        constraints = [
            models.UniqueConstraint(fields=["loan", "number"], name="loan_installment_unique_number"),
            models.CheckConstraint(condition=Q(number__gte=1), name="loan_installment_number_positive"),
            models.CheckConstraint(
                condition=Q(principal_due__gte=0) & Q(interest_due__gte=0),
                name="loan_installment_amounts_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.loan.reference} #{self.number} due {self.due_date}"

    @property
    def total_due(self):
        return self.principal_due + self.interest_due


class LoanRepayment(TimeStampedModel):
    """Detail for a LOAN_REPAYMENT ledger entry: how it splits into principal, interest and penalty."""

    transaction = models.OneToOneField(
        "ledger.Transaction", on_delete=models.PROTECT, related_name="loan_repayment"
    )
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    principal_component = MoneyField(default=0)
    interest_component = MoneyField(default=0)
    penalty_component = MoneyField(default=0)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(principal_component__gte=0) & Q(interest_component__gte=0) & Q(penalty_component__gte=0),
                name="loan_repayment_components_non_negative",
            ),
        ]

    def __str__(self):
        return f"Repayment {self.transaction.reference} on {self.loan.reference}"


class RepaymentAllocation(TimeStampedModel):
    """Portion of a repayment applied to one instalment (oldest first, interest before principal)."""

    repayment = models.ForeignKey(LoanRepayment, on_delete=models.PROTECT, related_name="allocations")
    installment = models.ForeignKey(
        RepaymentInstallment, on_delete=models.PROTECT, related_name="allocations"
    )
    principal_amount = MoneyField(default=0)
    interest_amount = MoneyField(default=0)

    class Meta(TimeStampedModel.Meta):
        constraints = [
            models.UniqueConstraint(fields=["repayment", "installment"], name="loan_allocation_unique"),
            models.CheckConstraint(
                condition=Q(principal_amount__gte=0) & Q(interest_amount__gte=0),
                name="loan_allocation_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(principal_amount__gt=0) | Q(interest_amount__gt=0),
                name="loan_allocation_not_empty",
            ),
        ]

    def __str__(self):
        return f"{self.repayment} → #{self.installment.number}"
