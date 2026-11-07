"""
Member-initiated account closure (ARCHITECTURE.md §6.4).

Submitting a request changes nothing about the account. An officer reviews and
approves it (the settlement statement is frozen at approval), then a separate
execute step settles balances and closes the membership. No records are deleted.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import ReferenceMixin, TimeStampedModel
from apps.common.uploads import closure_attachment_path
from apps.common.validators import document_extension_validator, validate_file_signature, validate_file_size


class AccountClosureRequest(ReferenceMixin, TimeStampedModel):
    REFERENCE_PREFIX = "CLS"

    class ReasonCategory(models.TextChoices):
        RETIREMENT = "RETIREMENT", "Retirement"
        RESIGNATION = "RESIGNATION", "Resignation from service"
        TRANSFER = "TRANSFER", "Transfer"
        PERSONAL = "PERSONAL", "Personal reasons"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CLOSED = "CLOSED", "Closed"
        WITHDRAWN = "WITHDRAWN", "Withdrawn by member"

    OPEN_STATUSES = [Status.SUBMITTED, Status.UNDER_REVIEW, Status.APPROVED]

    reference = models.CharField(max_length=30, unique=True, editable=False)
    member = models.ForeignKey(
        "members.Member", on_delete=models.PROTECT, related_name="closure_requests"
    )
    reason_category = models.CharField(max_length=15, choices=ReasonCategory.choices)
    reason = models.TextField()
    additional_information = models.TextField(blank=True)
    confirmed = models.BooleanField(
        help_text="Member confirmed they understand the consequences of closing their account."
    )
    attachment = models.FileField(
        upload_to=closure_attachment_path,
        blank=True,
        validators=[document_extension_validator, validate_file_size, validate_file_signature],
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SUBMITTED)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, help_text="Internal; never shown to the member.")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True, help_text="Shown to the member.")
    settlement_statement = models.JSONField(
        default=dict, blank=True, help_text="Balances and net position frozen at approval."
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        permissions = [
            ("view_closure_requests", "View account closure requests"),
            ("review_closure_request", "Review account closure requests"),
            ("approve_closure_request", "Approve or reject account closure requests"),
            ("execute_account_closure", "Settle and close approved accounts"),
        ]
        indexes = [models.Index(fields=["status", "created_at"], name="closures_request_queue")]
        constraints = [
            models.UniqueConstraint(
                fields=["member"],
                condition=Q(status__in=["SUBMITTED", "UNDER_REVIEW", "APPROVED"]),
                name="closure_one_open_request_per_member",
            ),
            models.CheckConstraint(condition=Q(confirmed=True), name="closure_request_confirmed"),
            models.CheckConstraint(
                condition=~Q(status__in=["APPROVED", "REJECTED", "CLOSED"]) | Q(decided_by__isnull=False),
                name="closure_request_decision_recorded",
            ),
            models.CheckConstraint(
                condition=~Q(status="CLOSED") | Q(closed_by__isnull=False, closed_at__isnull=False),
                name="closure_request_closure_recorded",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.member} ({self.get_status_display()})"
