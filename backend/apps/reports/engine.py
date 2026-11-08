"""
The report engine (ARCHITECTURE.md §7.4).

A report is one class: it declares its columns, which filters it accepts and
the permission needed to see it, and builds plain rows. The same result
then feeds three renderers: JSON (on-screen table), Excel and PDF.

    class MembersReport(Report):
        key = "members"
        columns = [Column("membership_number", "Membership no."), ...]
        filters = ("status", "department", "date_from", "date_to")
        def rows(self, f): ...
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.accounts.perms import P

TEXT, MONEY, DATE, INT, PERCENT = "text", "money", "date", "int", "percent"

# Rows shown on screen; exports carry everything up to their own limits.
SCREEN_ROWS = 500
XLSX_ROWS = 100_000
PDF_ROWS = 5_000


@dataclass
class Column:
    key: str
    label: str
    kind: str = TEXT
    total: bool = False  # add a totals row for this column (money/int only)


@dataclass
class Result:
    report: "Report"
    params: dict
    columns: list
    rows: list
    summary: list = field(default_factory=list)  # [(label, value, kind)]
    notes: list = field(default_factory=list)
    generated_at: object = field(default_factory=timezone.now)

    def totals(self):
        totals = {}
        for col in self.columns:
            if col.total:
                totals[col.key] = sum((r.get(col.key) or 0 for r in self.rows), Decimal("0.00") if col.kind == MONEY else 0)
        return totals


class FilterSerializer(serializers.Serializer):
    """Every filter a report may take. Each report uses only the ones it declares."""

    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    as_at = serializers.DateField(required=False)
    member = serializers.UUIDField(required=False)
    department = serializers.UUIDField(required=False)
    product = serializers.UUIDField(required=False)
    status = serializers.CharField(required=False, max_length=30)
    txn_type = serializers.CharField(required=False, max_length=40)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)

    def validate(self, attrs):
        if attrs.get("date_from") and attrs.get("date_to") and attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_to": ["Must be on or after the start date."]})
        return attrs


FILTER_LABELS = {
    "date_from": "From", "date_to": "To", "as_at": "Balances as at", "member": "Member", "department": "Department",
    "product": "Product", "status": "Status", "txn_type": "Transaction type", "year": "Year",
}


class Report:
    key = ""
    title = ""
    description = ""
    module = ""  # grouping in the catalogue
    permission = P.VIEW_REPORTS  # module permission, required on top of view_reports
    filters = ()
    required_filters = ()
    status_choices = ()
    txn_type_choices = ()
    columns = []
    landscape = True

    # -- to implement ----------------------------------------------------
    def rows(self, f):
        raise NotImplementedError

    def summary(self, rows, f):
        return []

    def get_columns(self, f):
        return self.columns

    # -- helpers -----------------------------------------------------------
    def defaults(self, f):
        """Fill in sensible defaults (e.g. as_at = today)."""
        if "as_at" in self.filters and not f.get("as_at"):
            f["as_at"] = timezone.localdate()
        if "year" in self.filters and not f.get("year"):
            f["year"] = timezone.localdate().year
        return f

    def clean(self, params):
        data = {k: v for k, v in params.items() if k in self.filters and v not in ("", None)}
        serializer = FilterSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        f = dict(serializer.validated_data)
        if "status" in f and self.status_choices and f["status"] not in dict(self.status_choices):
            raise serializers.ValidationError({"status": ["Not a valid choice for this report."]})
        if "txn_type" in f and self.txn_type_choices and f["txn_type"] not in dict(self.txn_type_choices):
            raise serializers.ValidationError({"txn_type": ["Not a valid choice for this report."]})
        missing = [name for name in self.required_filters if not f.get(name)]
        if missing:
            raise serializers.ValidationError({name: ["This filter is required for this report."] for name in missing})
        return self.defaults(f)

    def run(self, params):
        f = self.clean(params)
        rows = list(self.rows(f))
        return Result(report=self, params=f, columns=self.get_columns(f), rows=rows, summary=self.summary(rows, f))

    def describe(self, user):
        return {
            "key": self.key,
            "title": self.title,
            "description": self.description,
            "module": self.module,
            "filters": list(self.filters),
            "required_filters": list(self.required_filters),
            "status_choices": [{"value": v, "label": l} for v, l in self.status_choices],
            "txn_type_choices": [{"value": v, "label": l} for v, l in self.txn_type_choices],
            "can_export": user.has_perm(P.EXPORT_REPORTS),
        }


REGISTRY = {}


def register(cls):
    REGISTRY[cls.key] = cls()
    return cls


def available_reports(user):
    if not user.has_perm(P.VIEW_REPORTS):
        return []
    return [r for r in REGISTRY.values() if user.has_perm(r.permission)]


def get_report(user, key):
    report = REGISTRY.get(key)
    if report is None:
        raise NotFound("There is no such report.")
    if not (user.has_perm(P.VIEW_REPORTS) and user.has_perm(report.permission)):
        raise PermissionDenied("Your role does not include this report.")
    return report


def filter_description(result, lookups):
    """Human-readable list of the filters applied, e.g. [("Status", "Active"), ("From", "01 Jan 2026")]."""
    out = []
    for name, value in result.params.items():
        label = FILTER_LABELS.get(name, name)
        if isinstance(value, date):
            text = f"{value:%d %b %Y}"
        elif name == "status":
            text = dict(result.report.status_choices).get(value, value)
        elif name == "txn_type":
            text = dict(result.report.txn_type_choices).get(value, value)
        elif name in lookups:
            text = lookups[name](value)
        else:
            text = str(value)
        out.append((label, text))
    return out
