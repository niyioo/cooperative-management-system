from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import ReferenceMixin, TimeStampedModel
from apps.common.uploads import member_document_path, member_import_path, member_photo_path
from apps.common.validators import (
    document_extension_validator,
    image_extension_validator,
    spreadsheet_extension_validator,
    validate_file_signature,
    validate_file_size,
)


class MemberStatus(models.TextChoices):
    PENDING = "PENDING", "Pending activation"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"
    CLOSED = "CLOSED", "Closed"


class Member(TimeStampedModel):
    """
    A cooperative member: personal, employment and membership information.
    Financial positions are never stored here; they are derived from the ledger.
    Members are never deleted; closure is a status (BR-13).
    """

    class Title(models.TextChoices):
        MR = "MR", "Mr"
        MRS = "MRS", "Mrs"
        MISS = "MISS", "Miss"
        MS = "MS", "Ms"
        DR = "DR", "Dr"
        ENGR = "ENGR", "Engr"
        PROF = "PROF", "Prof"

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"

    class MaritalStatus(models.TextChoices):
        SINGLE = "SINGLE", "Single"
        MARRIED = "MARRIED", "Married"
        DIVORCED = "DIVORCED", "Divorced"
        WIDOWED = "WIDOWED", "Widowed"

    class EmploymentStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "In service"
        RETIRED = "RETIRED", "Retired"
        TRANSFERRED = "TRANSFERRED", "Transferred"
        RESIGNED = "RESIGNED", "Resigned"
        DECEASED = "DECEASED", "Deceased"

    Status = MemberStatus

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="member"
    )
    membership_number = models.CharField(max_length=30, unique=True, blank=True)

    # Personal
    title = models.CharField(max_length=10, choices=Title.choices, blank=True)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=10, choices=MaritalStatus.choices, blank=True)
    phone = models.CharField(max_length=20)
    alt_phone = models.CharField(max_length=20, blank=True)
    residential_address = models.TextField(blank=True)
    state_of_origin = models.CharField(max_length=50, blank=True)
    lga = models.CharField("LGA", max_length=100, blank=True)
    photo = models.ImageField(
        upload_to=member_photo_path,
        blank=True,
        validators=[image_extension_validator, validate_file_size, validate_file_signature],
    )

    # Employment
    staff_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    ippis_number = models.CharField("IPPIS number", max_length=30, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        "configuration.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="members",
    )
    unit = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    grade_level = models.CharField(max_length=20, blank=True)
    employment_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=15, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE
    )

    # Membership
    date_joined = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=MemberStatus.choices, default=MemberStatus.PENDING)
    status_reason = models.CharField(max_length=255, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # Bank details for payouts
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_number = models.CharField(max_length=10, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta(TimeStampedModel.Meta):
        ordering = ["last_name", "first_name"]
        permissions = [
            ("view_member", "View member records"),
            ("add_member", "Register members"),
            ("change_member", "Edit member records"),
            ("import_members", "Import members from a spreadsheet"),
            ("change_member_status", "Activate, suspend, reinstate or deactivate members"),
            ("manage_member_documents", "Upload and verify member documents"),
        ]
        indexes = [
            models.Index(fields=["status"], name="members_member_status"),
            models.Index(fields=["last_name", "first_name"], name="members_member_name"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status=MemberStatus.CLOSED, closed_at__isnull=False)
                    | (~Q(status=MemberStatus.CLOSED) & Q(closed_at__isnull=True))
                ),
                name="members_member_closed_at_matches_status",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.membership_number})"

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)

    def save(self, *args, **kwargs):
        # Unique nullable identifiers are stored as NULL, never "", so blanks don't collide.
        self.staff_number = (self.staff_number or "").strip() or None
        self.ippis_number = (self.ippis_number or "").strip() or None
        if not self.membership_number:
            self.membership_number = self.generate_membership_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_membership_number():
        from apps.common.sequences import next_value
        from apps.configuration.models import CooperativeSettings

        fmt = CooperativeSettings.load().membership_number_format
        return fmt.format(seq=next_value("MEMBERSHIP"), year=timezone.localdate().year)


class MembershipStatusChange(TimeStampedModel):
    """Full membership status history (the spec's Membership record). created_at is the change time."""

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="status_changes")
    from_status = models.CharField(max_length=10, choices=MemberStatus.choices, blank=True)
    to_status = models.CharField(max_length=10, choices=MemberStatus.choices)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    closure_request = models.ForeignKey(
        "closures.AccountClosureRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member.membership_number}: {self.from_status or '—'} → {self.to_status}"


class NextOfKin(TimeStampedModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="next_of_kin")
    full_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_primary = models.BooleanField(default=True)

    class Meta(TimeStampedModel.Meta):
        verbose_name_plural = "next of kin"
        ordering = ["-is_primary", "full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["member"], condition=Q(is_primary=True), name="members_one_primary_next_of_kin"
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"


class MemberDocument(TimeStampedModel):
    class DocumentType(models.TextChoices):
        PASSPORT_PHOTO = "PASSPORT_PHOTO", "Passport photograph"
        ID_CARD = "ID_CARD", "Identity card"
        APPOINTMENT_LETTER = "APPOINTMENT_LETTER", "Appointment letter"
        SIGNATURE = "SIGNATURE", "Signature specimen"
        OTHER = "OTHER", "Other"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=150, blank=True)
    file = models.FileField(
        upload_to=member_document_path,
        validators=[document_extension_validator, validate_file_size, validate_file_signature],
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.member.membership_number}"


class MemberImport(ReferenceMixin, TimeStampedModel):
    """
    A spreadsheet of members uploaded for bulk registration (e.g. at go-live).
    Upload validates every row (dry run) and stores the report; nothing is
    created until an officer commits an import with no errors.
    """

    REFERENCE_PREFIX = "IMP"

    class Status(models.TextChoices):
        READY = "READY", "Validated, ready to commit"
        HAS_ERRORS = "HAS_ERRORS", "Has errors"
        COMMITTED = "COMMITTED", "Committed"

    reference = models.CharField(max_length=30, unique=True, editable=False)
    source_file = models.FileField(
        upload_to=member_import_path,
        validators=[spreadsheet_extension_validator, validate_file_size, validate_file_signature],
    )
    original_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    report = models.JSONField(default=dict, blank=True)
    rows = models.JSONField(default=list, blank=True, help_text="Normalised row data committed on approval.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    committed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    committed_at = models.DateTimeField(null=True, blank=True)
    created_count = models.PositiveIntegerField(default=0)

    class Meta(TimeStampedModel.Meta):
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="COMMITTED") | Q(committed_by__isnull=False, committed_at__isnull=False),
                name="member_import_commit_recorded",
            ),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"
