"""Shared parsing for batch files whose rows identify members (payroll schedules, opening balances)."""
from apps.common.spreadsheets import SpreadsheetError, cell_text, map_columns, normalise_header

from .lookup import IDENTIFIER_FIELDS, members_by_identifier

IDENTIFIER_LABELS = {
    "membership_number": "Membership number",
    "staff_number": "Staff number",
    "ippis_number": "IPPIS number",
}


def column_aliases(columns):
    aliases = {}
    for key, label in columns.items():
        aliases[key] = key
        aliases[normalise_header(label)] = key
    return aliases


def batch_report(total, errors, unknown):
    return {
        "total_rows": total,
        "valid_rows": total - len(errors),
        "error_rows": len(errors),
        "errors": errors,
        "unknown_columns": unknown,
        "file_errors": [],
    }


class MemberRowsMixin:
    """Shared parsing: find each row's member by membership, staff or IPPIS number."""

    columns = {}
    required = {}

    def _read(self, header, data):
        mapping, unknown = map_columns(header, column_aliases(self.columns), self.required)
        if not any(k in mapping.values() for k in IDENTIFIER_FIELDS):
            raise SpreadsheetError(
                "Add a column that identifies members: Membership number, Staff number or IPPIS number."
            )
        rows = []
        for row_number, cells in data:
            values = {key: (cells[i] if i < len(cells) else None) for i, key in mapping.items()}
            rows.append((row_number, values))
        wanted = {f: {cell_text(v.get(f)).upper() for _, v in rows if cell_text(v.get(f))} for f in IDENTIFIER_FIELDS}
        return rows, unknown, members_by_identifier(wanted)

    @staticmethod
    def _member_for(values, members, errors):
        for field in IDENTIFIER_FIELDS:
            key = cell_text(values.get(field)).upper()
            if key:
                member = members.get((field, key))
                if member is None:
                    errors[field] = [f"No member has {IDENTIFIER_LABELS[field].lower()} {key}."]
                return member
        errors["membership_number"] = ["Identify the member (membership, staff or IPPIS number)."]
        return None

