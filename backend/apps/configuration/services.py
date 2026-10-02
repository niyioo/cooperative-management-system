from django.db import transaction

from apps.accounts.permissions import require_perm
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.exceptions import DomainError

from .models import CooperativeSettings, Department


def _assert_unique(name, code, exclude_pk=None):
    qs = Department.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if name and qs.filter(name__iexact=name.strip()).exists():
        raise DomainError("A department with this name already exists.", code="duplicate_name",
                          fields={"name": ["A department with this name already exists."]})
    if code and qs.filter(code__iexact=code.strip()).exists():
        raise DomainError("A department with this code already exists.", code="duplicate_code",
                          fields={"code": ["A department with this code already exists."]})


@transaction.atomic
def create_department(actor, *, name, code=None, is_active=True):
    require_perm(actor, P.MANAGE_SETTINGS)
    _assert_unique(name, code)
    department = Department.objects.create(name=name.strip(), code=code, is_active=is_active)
    record("department.created", actor=actor, obj=department)
    return department


@transaction.atomic
def update_department(actor, department, **data):
    """Departments are deactivated, never deleted: members keep their history."""
    require_perm(actor, P.MANAGE_SETTINGS)
    _assert_unique(data.get("name"), data.get("code"), exclude_pk=department.pk)
    changes = {}
    for field, value in data.items():
        if getattr(department, field) != value:
            changes[field] = [getattr(department, field), value]
            setattr(department, field, value)
    if changes:
        department.save()
        record("department.updated", actor=actor, obj=department, changes=changes)
    return department


SETTINGS_FIELDS = [
    "name",
    "short_name",
    "parent_institution",
    "registration_number",
    "address",
    "email",
    "phone",
    "currency_code",
    "membership_number_format",
    "financial_year_start_month",
    "dividend_processing_month",
    "member_withdrawal_requests_enabled",
    "closure_disables_portal_login",
    "maker_checker_types",
    "loan_overdue_grace_days",
    "contributions_tracked_from",
    "session_idle_timeout_minutes",
]


def _validate_settings(data):
    fmt = data.get("membership_number_format")
    if fmt is not None:
        try:
            sample = fmt.format(seq=1, year=2026)
        except (KeyError, IndexError, ValueError):
            sample = None
        if "{seq" not in fmt or sample is None:
            raise DomainError(
                "The format must contain {seq}, e.g. EMDI/COOP/{seq:04d}; {year} is optional.",
                code="invalid_format",
                fields={"membership_number_format": ["Must contain {seq}."]},
            )


@transaction.atomic
def update_settings(actor, **data):
    require_perm(actor, P.MANAGE_SETTINGS)
    _validate_settings(data)
    if data.get("contributions_tracked_from"):
        data["contributions_tracked_from"] = data["contributions_tracked_from"].replace(day=1)  # a month
    settings_row = CooperativeSettings.objects.select_for_update().get(pk=CooperativeSettings.load().pk)
    changes = {}
    for field in SETTINGS_FIELDS:
        if field in data and getattr(settings_row, field) != data[field]:
            changes[field] = [getattr(settings_row, field), data[field]]
            setattr(settings_row, field, data[field])
    if changes:
        settings_row.save()
        record("settings.updated", actor=actor, obj=settings_row, changes=changes)
    return settings_row
