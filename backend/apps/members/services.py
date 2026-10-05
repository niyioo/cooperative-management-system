"""
Member management (ARCHITECTURE.md §6.1). Every change is permission-checked,
audited, and refused for the officer's own member record (BR-18).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.functions import Upper
from django.utils import timezone

from apps.accounts import services as account_services
from apps.accounts.emails import send_activation_email
from apps.accounts.models import is_placeholder_email, placeholder_email
from apps.accounts.permissions import assert_not_self, require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError
from apps.common.spreadsheets import SpreadsheetError
from apps.configuration.models import Department
from apps.savings.models import ProductKind, SavingsAccount, SavingsProduct

from . import importer
from .models import Member, MemberDocument, MemberImport, MemberStatus, MembershipStatusChange, NextOfKin

User = get_user_model()

PROFILE_FIELDS = [
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

INITIAL_STATUSES = {MemberStatus.PENDING, MemberStatus.ACTIVE, MemberStatus.INACTIVE}

# action: (allowed current statuses, new status, reason required)
STATUS_TRANSITIONS = {
    "activate": ({MemberStatus.PENDING}, MemberStatus.ACTIVE, False),
    "suspend": ({MemberStatus.ACTIVE}, MemberStatus.SUSPENDED, True),
    "reinstate": ({MemberStatus.SUSPENDED}, MemberStatus.ACTIVE, False),
    "deactivate": ({MemberStatus.PENDING, MemberStatus.ACTIVE, MemberStatus.SUSPENDED}, MemberStatus.INACTIVE, True),
    "reactivate": ({MemberStatus.INACTIVE}, MemberStatus.ACTIVE, False),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field_error(field, message, code):
    raise DomainError(message, code=code, fields={field: [message]})


def _assert_editable(member):
    if member.status == MemberStatus.CLOSED:
        raise DomainError("This membership is closed; its records are read-only.", code="member_closed")


def _assert_unique_identifiers(*, membership_number=None, staff_number=None, ippis_number=None, exclude_pk=None):
    checks = [
        ("membership_number", membership_number, "This membership number is already in use."),
        ("staff_number", staff_number, "Another member already has this staff number."),
        ("ippis_number", ippis_number, "Another member already has this IPPIS number."),
    ]
    for field, value, message in checks:
        if not value:
            continue
        qs = Member.objects.annotate(_v=Upper(field)).filter(_v=value.strip().upper())
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        if qs.exists():
            _field_error(field, message, f"duplicate_{field}")


def _display(value):
    """Readable value for audit diffs (FKs by name, dates ISO)."""
    if value is None:
        return None
    if hasattr(value, "pk"):
        return str(value)
    return value


def _unique_placeholder_email(membership_number):
    email = placeholder_email(membership_number)
    candidate, n = email, 1
    while User.objects.filter(email__iexact=candidate).exists():
        n += 1
        local, domain = email.split("@")
        candidate = f"{local}-{n}@{domain}"
    return candidate


def open_mandatory_accounts(member):
    """Open an account in every active mandatory regular savings product (e.g. Regular Savings)."""
    products = SavingsProduct.objects.filter(is_active=True, is_mandatory=True, kind=ProductKind.REGULAR)
    for product in products:
        SavingsAccount.objects.get_or_create(member=member, product=product, cycle=None)


def _log_status(member, from_status, to_status, reason, actor, closure_request=None):
    MembershipStatusChange.objects.create(
        member=member,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        changed_by=actor,
        closure_request=closure_request,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def create_member_record(actor, *, profile, email="", membership_number="", status=MemberStatus.PENDING,
                         next_of_kin=None, reason="Registered"):
    """
    Create the user account, member profile, status history, next of kin and
    mandatory savings accounts. Callers must check permissions and audit.
    """
    if status not in INITIAL_STATUSES:
        raise DomainError("New members can only start as Pending, Active or Inactive.", code="invalid_status")
    membership_number = (membership_number or "").strip()
    email = (email or "").strip().lower()
    _assert_unique_identifiers(
        membership_number=membership_number,
        staff_number=profile.get("staff_number"),
        ippis_number=profile.get("ippis_number"),
    )

    user = None
    if email:
        user = User.objects.filter(email__iexact=email).first()
        if user is not None and hasattr(user, "member"):
            _field_error("email", "A member with this email address already exists.", "duplicate_email")

    membership_number = membership_number or Member.generate_membership_number()
    if user is None:
        user = User.objects.create_user(
            email=email or _unique_placeholder_email(membership_number),
            first_name=profile["first_name"],
            last_name=profile["last_name"],
            phone=profile.get("phone", ""),
        )

    member = Member(user=user, membership_number=membership_number, status=status, created_by=actor, **profile)
    member.save()
    _log_status(member, "", status, reason, actor)
    if next_of_kin:
        NextOfKin.objects.create(member=member, is_primary=True, **next_of_kin)
    open_mandatory_accounts(member)
    return member


@transaction.atomic
def register_member(actor, *, profile, email="", membership_number="", status=MemberStatus.PENDING,
                    next_of_kin=None, send_activation=True):
    require_perm(actor, P.ADD_MEMBER)
    if status != MemberStatus.PENDING:
        require_perm(actor, P.CHANGE_MEMBER_STATUS)
    member = create_member_record(
        actor,
        profile=profile,
        email=email,
        membership_number=membership_number,
        status=status,
        next_of_kin=next_of_kin,
    )
    user = member.user
    will_email = send_activation and user.has_real_email and not user.has_usable_password()
    record(
        "member.created",
        actor=actor,
        obj=member,
        metadata={"status": status, "activation_email": will_email, "linked_existing_account": user.has_usable_password()},
    )
    if will_email:
        transaction.on_commit(lambda: send_activation_email(user))
    return member


# ---------------------------------------------------------------------------
# Profile changes
# ---------------------------------------------------------------------------

@transaction.atomic
def update_member(actor, member, **data):
    require_perm(actor, P.CHANGE_MEMBER)
    assert_not_self(actor, member, "edit")
    member = Member.objects.select_for_update(of=("self",)).select_related("user").get(pk=member.pk)
    _assert_editable(member)

    changes = {}
    user_fields = set()

    new_number = data.pop("membership_number", None)
    if new_number is not None and new_number.strip() and new_number.strip() != member.membership_number:
        _assert_unique_identifiers(membership_number=new_number, exclude_pk=member.pk)
        changes["membership_number"] = [member.membership_number, new_number.strip()]
        member.membership_number = new_number.strip()

    new_email = (data.pop("email", None) or "").strip().lower()
    if new_email and new_email != member.user.email:
        if User.objects.filter(email__iexact=new_email).exclude(pk=member.user_id).exists():
            _field_error("email", "This email address belongs to another account.", "duplicate_email")
        changes["email"] = [None if is_placeholder_email(member.user.email) else member.user.email, new_email]
        member.user.email = new_email
        user_fields.add("email")

    _assert_unique_identifiers(
        staff_number=data.get("staff_number"), ippis_number=data.get("ippis_number"), exclude_pk=member.pk
    )
    for field in PROFILE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field in ("staff_number", "ippis_number"):
            value = (value or "").strip() or None
        if getattr(member, field) != value:
            changes[field] = [_display(getattr(member, field)), _display(value)]
            setattr(member, field, value)

    if not changes:
        return member

    member.save()
    for member_field, user_field in (("first_name", "first_name"), ("last_name", "last_name"), ("phone", "phone")):
        if member_field in changes:
            setattr(member.user, user_field, getattr(member, member_field))
            user_fields.add(user_field)
    if user_fields:
        member.user.save(update_fields=[*user_fields, "updated_at"])
    record("member.updated", actor=actor, obj=member, changes=changes)
    return member


@transaction.atomic
def change_member_status(actor, member, action, *, reason=""):
    require_perm(actor, P.CHANGE_MEMBER_STATUS)
    assert_not_self(actor, member, "change the status of")
    if action not in STATUS_TRANSITIONS:
        raise DomainError("Unknown status action.", code="invalid_action")
    allowed_from, new_status, reason_required = STATUS_TRANSITIONS[action]
    member = Member.objects.select_for_update().get(pk=member.pk)
    if member.status not in allowed_from:
        raise DomainError(
            f"A {member.get_status_display().lower()} member cannot be {action}d.", code="invalid_transition"
        )
    reason = (reason or "").strip()
    if reason_required and not reason:
        _field_error("reason", "Please give a reason.", "reason_required")

    old_status = member.status
    member.status = new_status
    member.status_reason = reason
    member.save(update_fields=["status", "status_reason", "updated_at"])
    _log_status(member, old_status, new_status, reason, actor)
    record(
        "member.status_changed",
        actor=actor,
        obj=member,
        changes={"status": [old_status, new_status]},
        metadata={"action": action, "reason": reason},
    )
    return member


@transaction.atomic
def set_member_photo(actor, member, photo):
    require_perm(actor, P.CHANGE_MEMBER)
    assert_not_self(actor, member, "edit")
    _assert_editable(member)
    member.photo = photo
    member.save(update_fields=["photo", "updated_at"])
    record("member.photo_updated", actor=actor, obj=member)
    return member


# ---------------------------------------------------------------------------
# Next of kin
# ---------------------------------------------------------------------------

def _demote_other_primaries(member, keep_pk=None):
    qs = NextOfKin.objects.filter(member=member, is_primary=True)
    if keep_pk:
        qs = qs.exclude(pk=keep_pk)
    qs.update(is_primary=False)


@transaction.atomic
def add_next_of_kin(actor, member, **data):
    require_perm(actor, P.CHANGE_MEMBER)
    assert_not_self(actor, member, "edit")
    _assert_editable(member)
    is_primary = data.pop("is_primary", None)
    if is_primary is None:
        is_primary = not member.next_of_kin.exists()
    if is_primary:
        _demote_other_primaries(member)
    kin = NextOfKin.objects.create(member=member, is_primary=is_primary, **data)
    record("member.next_of_kin_added", actor=actor, obj=member, metadata={"next_of_kin": kin.full_name})
    return kin


@transaction.atomic
def update_next_of_kin(actor, kin, **data):
    member = kin.member
    require_perm(actor, P.CHANGE_MEMBER)
    assert_not_self(actor, member, "edit")
    _assert_editable(member)
    if data.get("is_primary") is None:
        data.pop("is_primary", None)
    changes = {}
    if data.get("is_primary"):
        _demote_other_primaries(member, keep_pk=kin.pk)
    for field, value in data.items():
        if getattr(kin, field) != value:
            changes[field] = [getattr(kin, field), value]
            setattr(kin, field, value)
    if changes:
        kin.save()
        record("member.next_of_kin_updated", actor=actor, obj=member, changes=changes, metadata={"next_of_kin": kin.full_name})
    return kin


@transaction.atomic
def remove_next_of_kin(actor, kin):
    member = kin.member
    require_perm(actor, P.CHANGE_MEMBER)
    assert_not_self(actor, member, "edit")
    _assert_editable(member)
    record("member.next_of_kin_removed", actor=actor, obj=member, metadata={"next_of_kin": kin.full_name})
    kin.delete()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@transaction.atomic
def upload_document(actor, member, *, document_type, file, title=""):
    require_perm(actor, P.MANAGE_MEMBER_DOCUMENTS)
    _assert_editable(member)
    document = MemberDocument.objects.create(
        member=member, document_type=document_type, title=title, file=file, uploaded_by=actor
    )
    record(
        "member.document_uploaded",
        actor=actor,
        obj=member,
        metadata={"document_id": str(document.pk), "document_type": document_type, "title": title},
    )
    return document


@transaction.atomic
def verify_document(actor, document):
    require_perm(actor, P.MANAGE_MEMBER_DOCUMENTS)
    assert_not_self(actor, document.member, "verify documents on")
    if document.verified_at:
        raise DomainError("This document has already been verified.", code="already_verified")
    document.verified_by = actor
    document.verified_at = timezone.now()
    document.save(update_fields=["verified_by", "verified_at", "updated_at"])
    record("member.document_verified", actor=actor, obj=document.member, metadata={"document_id": str(document.pk)})
    return document


@transaction.atomic
def remove_document(actor, document):
    """Only unverified documents (e.g. uploaded in error) can be removed; verified ones are part of the record."""
    require_perm(actor, P.MANAGE_MEMBER_DOCUMENTS)
    assert_not_self(actor, document.member, "remove documents from")
    if document.verified_at:
        raise DomainError("Verified documents cannot be removed.", code="document_verified")
    record(
        "member.document_removed",
        actor=actor,
        obj=document.member,
        metadata={"document_id": str(document.pk), "document_type": document.document_type, "title": document.title},
    )
    document.file.delete(save=False)
    document.delete()


# ---------------------------------------------------------------------------
# Portal account
# ---------------------------------------------------------------------------

def send_member_activation(actor, member):
    if not member.user.has_real_email:
        raise DomainError(
            "This member has no email address. Issue a temporary password instead.", code="no_email"
        )
    assert_not_self(actor, member, "manage the portal account of")
    account_services.resend_activation(actor, member.user, permission=P.CHANGE_MEMBER)


def issue_member_temporary_password(actor, member):
    assert_not_self(actor, member, "manage the portal account of")
    if not member.user.is_active:
        raise DomainError("This member's portal account is deactivated.", code="inactive_account")
    return account_services.issue_temporary_password(actor, member.user, permission=P.CHANGE_MEMBER)



# ---------------------------------------------------------------------------
# Bulk import
# ---------------------------------------------------------------------------

DATE_FIELDS = ("date_of_birth", "employment_date", "date_joined")


@transaction.atomic
def create_import(actor, uploaded_file):
    """Validate a spreadsheet (dry run) and store the report. Nothing is created yet."""
    require_perm(actor, P.IMPORT_MEMBERS)
    try:
        header, data = importer.read_member_table(uploaded_file)
        rows, report = importer.validate_table(header, data)
    except SpreadsheetError as exc:
        rows = []
        report = {
            "total_rows": 0,
            "valid_rows": 0,
            "error_rows": 0,
            "errors": [],
            "unknown_columns": [],
            "file_errors": [str(exc)],
        }
    ready = not report["file_errors"] and report["error_rows"] == 0
    member_import = MemberImport.objects.create(
        source_file=uploaded_file,
        original_filename=(uploaded_file.name or "")[:255],
        status=MemberImport.Status.READY if ready else MemberImport.Status.HAS_ERRORS,
        total_rows=report["total_rows"],
        valid_rows=report["valid_rows"],
        report=report,
        rows=rows if ready else [],  # keep personal data only when it will actually be imported
        created_by=actor,
    )
    record(
        "member.import_uploaded",
        actor=actor,
        obj=member_import,
        metadata={"rows": report["total_rows"], "error_rows": report["error_rows"], "file_errors": report["file_errors"]},
    )
    return member_import


def _profile_from_row(values, departments):
    profile = {field: values[field] for field in PROFILE_FIELDS if field in values}
    for field in DATE_FIELDS:
        raw = profile.get(field)
        if raw:
            profile[field] = date.fromisoformat(raw)
        else:
            profile.pop(field, None)  # model default (date_joined = today) applies
    profile["department"] = departments.get(values.get("department")) if values.get("department") else None
    kin = None
    if values.get("next_of_kin_name"):
        kin = {
            "full_name": values["next_of_kin_name"],
            "relationship": values["next_of_kin_relationship"],
            "phone": values["next_of_kin_phone"],
        }
    return profile, kin


@transaction.atomic
def _commit_import(actor, member_import, send_activation):
    member_import = MemberImport.objects.select_for_update().get(pk=member_import.pk)
    if member_import.status != MemberImport.Status.READY:
        raise DomainError("Only a validated import with no errors can be committed.", code="import_not_ready")

    conflicts = importer.revalidate_stored_rows(member_import.rows)
    if conflicts:
        member_import.status = MemberImport.Status.HAS_ERRORS
        member_import.valid_rows = member_import.total_rows - len(conflicts)
        member_import.report = {**member_import.report, "errors": conflicts, "error_rows": len(conflicts)}
        member_import.rows = []
        member_import.save(update_fields=["status", "valid_rows", "report", "rows", "updated_at"])
        return None, conflicts

    departments = {str(d.pk): d for d in Department.objects.all()}
    created = []
    for row in member_import.rows:
        values = row["values"]
        profile, kin = _profile_from_row(values, departments)
        member = create_member_record(
            actor,
            profile=profile,
            email=values.get("email", ""),
            membership_number=values.get("membership_number", ""),
            status=values["status"],
            next_of_kin=kin,
            reason=f"Imported ({member_import.reference}, row {row['row']})",
        )
        record("member.created", actor=actor, obj=member, metadata={"import": member_import.reference, "row": row["row"]})
        created.append(member)

    member_import.status = MemberImport.Status.COMMITTED
    member_import.committed_by = actor
    member_import.committed_at = timezone.now()
    member_import.created_count = len(created)
    member_import.rows = []
    member_import.save()
    record(
        "member.import_committed",
        actor=actor,
        obj=member_import,
        metadata={"created": len(created), "activation_emails": send_activation},
    )
    if send_activation:
        users = [m.user for m in created if m.user.has_real_email and not m.user.has_usable_password()]
        transaction.on_commit(lambda: [send_activation_email(u) for u in users])
    return member_import, None


def commit_import(actor, member_import, *, send_activation=False):
    """Create every member in a validated import, all or nothing."""
    require_perm(actor, P.IMPORT_MEMBERS, P.CHANGE_MEMBER_STATUS)
    member_import, conflicts = _commit_import(actor, member_import, send_activation)
    if conflicts:
        raise DomainError(
            f"{len(conflicts)} row(s) now conflict with existing records. Correct the file and upload it again.",
            code="import_conflicts",
            fields={"rows": conflicts},
        )
    return member_import
