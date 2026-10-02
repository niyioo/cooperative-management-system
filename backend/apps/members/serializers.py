import re
from datetime import date

from rest_framework import serializers

from apps.accounts.models import is_placeholder_email
from apps.common.serializers import validate_model_field
from apps.configuration.models import Department

from .models import Member, MemberDocument, MemberImport, MemberStatus, MembershipStatusChange, NextOfKin

PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def clean_phone(value):
    value = re.sub(r"[\s\-()]", "", value or "")
    if value and not PHONE_RE.match(value):
        raise serializers.ValidationError("Enter a valid phone number, e.g. 08031234567 or +2348031234567.")
    return value


class DepartmentSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code"]


# ---------------------------------------------------------------------------
# Next of kin
# ---------------------------------------------------------------------------

class NextOfKinSerializer(serializers.ModelSerializer):
    # Nullable so "not sent" (None) differs from False, including in multipart forms,
    # where a missing boolean would otherwise read as False. None = let the service decide.
    is_primary = serializers.BooleanField(required=False, allow_null=True)

    class Meta:
        model = NextOfKin
        fields = ["id", "full_name", "relationship", "phone", "email", "address", "is_primary"]
        read_only_fields = ["id"]

    def validate_phone(self, value):
        return clean_phone(value)


class NextOfKinInputSerializer(NextOfKinSerializer):
    """Used when registering a member: always becomes the primary next of kin."""

    class Meta(NextOfKinSerializer.Meta):
        fields = ["full_name", "relationship", "phone", "email", "address"]


# ---------------------------------------------------------------------------
# Member read serializers
# ---------------------------------------------------------------------------

def _real_email(user):
    return None if is_placeholder_email(user.email) else user.email


class MemberListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    email = serializers.SerializerMethodField()
    department = DepartmentSummarySerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    has_photo = serializers.SerializerMethodField()

    class Meta:
        model = Member
        fields = [
            "id",
            "membership_number",
            "title",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "staff_number",
            "department",
            "status",
            "status_label",
            "date_joined",
            "has_photo",
        ]

    def get_email(self, obj) -> str | None:
        return _real_email(obj.user)

    def get_has_photo(self, obj) -> bool:
        return bool(obj.photo)


class StatusChangeSerializer(serializers.ModelSerializer):
    changed_by = serializers.CharField(source="changed_by.full_name", default=None, read_only=True)

    class Meta:
        model = MembershipStatusChange
        fields = ["from_status", "to_status", "reason", "changed_by", "created_at"]


class MemberDetailSerializer(MemberListSerializer):
    next_of_kin = NextOfKinSerializer(many=True, read_only=True)
    status_history = serializers.SerializerMethodField()
    portal = serializers.SerializerMethodField()
    document_count = serializers.IntegerField(source="documents.count", read_only=True)
    created_by = serializers.CharField(source="created_by.full_name", default=None, read_only=True)

    class Meta(MemberListSerializer.Meta):
        fields = MemberListSerializer.Meta.fields + [
            "middle_name",
            "gender",
            "date_of_birth",
            "marital_status",
            "alt_phone",
            "residential_address",
            "state_of_origin",
            "lga",
            "ippis_number",
            "unit",
            "designation",
            "grade_level",
            "employment_date",
            "employment_status",
            "status_reason",
            "closed_at",
            "bank_name",
            "bank_account_number",
            "bank_account_name",
            "next_of_kin",
            "status_history",
            "portal",
            "document_count",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def get_status_history(self, obj) -> list[dict]:
        changes = obj.status_changes.select_related("changed_by")[:20]
        return StatusChangeSerializer(changes, many=True).data

    def get_portal(self, obj) -> dict:
        user = obj.user
        return {
            "has_email": not is_placeholder_email(user.email),
            "activated": user.has_usable_password(),
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
            "last_login": user.last_login,
        }


# ---------------------------------------------------------------------------
# Member write serializers
# ---------------------------------------------------------------------------

class MemberProfileSerializer(serializers.ModelSerializer):
    """Shared validation for the editable profile fields."""

    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.filter(is_active=True), allow_null=True, required=False
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    membership_number = serializers.CharField(max_length=30, required=False, allow_blank=True)

    class Meta:
        model = Member
        fields = [
            "membership_number",
            "email",
            "title",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "date_of_birth",
            "marital_status",
            "phone",
            "alt_phone",
            "residential_address",
            "state_of_origin",
            "lga",
            "staff_number",
            "ippis_number",
            "department",
            "unit",
            "designation",
            "grade_level",
            "employment_date",
            "employment_status",
            "date_joined",
            "bank_name",
            "bank_account_number",
            "bank_account_name",
        ]
        # Uniqueness is checked case-insensitively in the service layer.
        extra_kwargs = {
            "staff_number": {"validators": [], "allow_blank": True},
            "ippis_number": {"validators": [], "allow_blank": True},
        }

    def validate_phone(self, value):
        return clean_phone(value)

    def validate_alt_phone(self, value):
        return clean_phone(value)

    def validate_date_of_birth(self, value):
        if value and value >= date.today():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return value

    def validate_employment_date(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Cannot be in the future.")
        return value

    def validate_date_joined(self, value):
        if value and value > date.today():
            raise serializers.ValidationError("Cannot be in the future.")
        return value

    def validate_bank_account_number(self, value):
        if value and not re.fullmatch(r"\d{10}", value):
            raise serializers.ValidationError("Bank account numbers have exactly 10 digits.")
        return value


class MemberCreateSerializer(MemberProfileSerializer):
    status = serializers.ChoiceField(
        choices=[(MemberStatus.PENDING, "Pending activation"), (MemberStatus.ACTIVE, "Active")],
        default=MemberStatus.PENDING,
    )
    send_activation = serializers.BooleanField(default=True)
    next_of_kin = NextOfKinInputSerializer(required=False)

    class Meta(MemberProfileSerializer.Meta):
        fields = MemberProfileSerializer.Meta.fields + ["status", "send_activation", "next_of_kin"]


class StatusActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Documents, photo, imports
# ---------------------------------------------------------------------------

class MemberDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="uploaded_by.full_name", default=None, read_only=True)
    verified_by = serializers.CharField(source="verified_by.full_name", default=None, read_only=True)
    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    file = serializers.FileField(write_only=True)
    size = serializers.SerializerMethodField()

    class Meta:
        model = MemberDocument
        fields = [
            "id",
            "document_type",
            "document_type_label",
            "title",
            "file",
            "size",
            "uploaded_by",
            "verified_by",
            "verified_at",
            "created_at",
        ]
        read_only_fields = ["id", "verified_at", "created_at"]

    def validate_file(self, value):
        return validate_model_field(MemberDocument, "file", value)

    def get_size(self, obj) -> int | None:
        try:
            return obj.file.size
        except (OSError, ValueError):
            return None


class PhotoSerializer(serializers.Serializer):
    photo = serializers.ImageField()

    def validate_photo(self, value):
        return validate_model_field(Member, "photo", value)


class MemberImportSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.full_name", read_only=True)
    committed_by = serializers.CharField(source="committed_by.full_name", default=None, read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = MemberImport
        fields = [
            "id",
            "reference",
            "original_filename",
            "status",
            "status_label",
            "total_rows",
            "valid_rows",
            "report",
            "created_by",
            "created_at",
            "committed_by",
            "committed_at",
            "created_count",
        ]


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        return validate_model_field(MemberImport, "source_file", value)


class ImportCommitSerializer(serializers.Serializer):
    send_activation = serializers.BooleanField(default=False)
