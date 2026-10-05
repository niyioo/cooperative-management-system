"""LOAN_REPAYMENTS batches: monthly payroll loan deductions."""
from collections import defaultdict

from django.utils import timezone

from apps.accounts.perms import P
from apps.common.spreadsheets import (
    SpreadsheetError,
    build_template,
    cell_text,
    map_columns,
    normalise_header,
    parse_amount,
    parse_period,
)
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchType, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.lookup import IDENTIFIER_FIELDS, members_by_identifier

from .models import Loan
from .services import repayable

COLUMNS = {
    "membership_number": "Membership number",
    "staff_number": "Staff number",
    "ippis_number": "IPPIS number",
    "name": "Name",
    "loan": "Loan reference",
    "amount": "Amount",
    "period": "Month",
    "reference": "Reference",
}
ALIASES = {**{k: k for k in COLUMNS}, **{normalise_header(v): k for k, v in COLUMNS.items()}}


def _payroll_months(running, exclude_batch=None):
    """
    {(loan id, month)} already covered by a payroll batch (posted or awaiting
    approval), so the same month's deduction cannot be posted twice. Single
    repayments outside payroll (cash, transfers) don't count.
    """
    loan_ids = [loan.pk for loans in running.values() for loan in loans]
    entries = Transaction.objects.filter(
        loan__in=loan_ids,
        txn_type=TransactionType.LOAN_REPAYMENT,
        batch__batch_type=BatchType.LOAN_REPAYMENTS,
        status__in=[TransactionStatus.POSTED, TransactionStatus.PENDING],
        period__isnull=False,
    )
    if exclude_batch is not None:
        entries = entries.exclude(batch=exclude_batch)
    return set(entries.values_list("loan_id", "period"))


class LoanRepaymentBatchHandler(BatchHandler):
    batch_type = BatchType.LOAN_REPAYMENTS
    permissions = (P.RECORD_LOAN_REPAYMENT,)
    file_options = ("period",)

    def validate_file(self, header, data, options):
        mapping, unknown = map_columns(header, ALIASES, {"amount": "Amount"})
        if not any(k in mapping.values() for k in IDENTIFIER_FIELDS):
            raise SpreadsheetError("Add a column that identifies members: Membership number, Staff number or IPPIS number.")
        rows = [(n, {key: (cells[i] if i < len(cells) else None) for i, key in mapping.items()}) for n, cells in data]
        wanted = {f: {cell_text(v.get(f)).upper() for _, v in rows if cell_text(v.get(f))} for f in IDENTIFIER_FIELDS}
        members = members_by_identifier(wanted)

        running = defaultdict(list)
        for loan in Loan.objects.filter(member__in={m.pk for m in members.values()}, status__in=Loan.RUNNING_STATUSES):
            running[loan.member_id].append(loan)

        default_period = options.get("period")
        claimed = defaultdict(lambda: 0)  # amount per loan claimed by earlier rows
        in_file = {}  # (loan, month) -> first row number, to catch a repeated row
        already = _payroll_months(running)
        lines, errors = [], []
        for row_number, values in rows:
            row_errors = {}
            member = None
            for field in IDENTIFIER_FIELDS:
                key = cell_text(values.get(field)).upper()
                if key:
                    member = members.get((field, key))
                    if member is None:
                        row_errors[field] = [f"No member has {COLUMNS[field].lower()} {key}."]
                    break
            else:
                row_errors["membership_number"] = ["Identify the member (membership, staff or IPPIS number)."]

            loan = None
            if member is not None:
                reference = cell_text(values.get("loan")).upper()
                loans = running.get(member.pk, [])
                if reference:
                    loan = next((l for l in loans if l.reference.upper() == reference), None)
                    if loan is None:
                        row_errors["loan"] = [f"{member.full_name} has no running loan {reference}."]
                elif len(loans) == 1:
                    loan = loans[0]
                elif not loans:
                    row_errors["loan"] = [f"{member.full_name} has no running loan."]
                else:
                    row_errors["loan"] = [f"{member.full_name} has {len(loans)} running loans; add the Loan reference."]

            try:
                amount = parse_amount(values.get("amount"))
            except ValueError as exc:
                row_errors["amount"] = [str(exc)]
                amount = None
            try:
                period = parse_period(values.get("period")) or default_period or timezone.localdate().replace(day=1)
            except ValueError as exc:
                row_errors["period"] = [str(exc)]
                period = None

            if loan is not None and period is not None:
                key = (loan.pk, period)
                if key in already:
                    row_errors["period"] = [f"Payroll repayments for {loan.reference} in {period:%B %Y} have already been recorded."]
                elif key in in_file:
                    row_errors["period"] = [f"{loan.reference} for {period:%B %Y} is already on row {in_file[key]}."]
                else:
                    in_file[key] = row_number

            if loan is not None and amount is not None and not row_errors:
                available = repayable(loan) - claimed[loan.pk]
                if amount > available:
                    row_errors["amount"] = [f"More than the ₦{available:,.2f} still owed on {loan.reference}."]
                else:
                    claimed[loan.pk] += amount

            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append({"loan": loan, "amount": amount, "period": period, "reference": cell_text(values.get("reference"))[:100]})

        report = {
            "total_rows": len(rows),
            "valid_rows": len(rows) - len(errors),
            "error_rows": len(errors),
            "errors": errors,
            "unknown_columns": unknown,
            "file_errors": [],
        }
        return lines, report

    def create_lines(self, actor, batch, lines):
        for line in lines:
            loan = line["loan"]
            ledger.create_entry(
                actor,
                member=loan.member,
                txn_type=TransactionType.LOAN_REPAYMENT,
                amount=line["amount"],
                account=loan,
                period=line["period"],
                description=f"Repayment of {loan.reference} (payroll {line['period']:%b %Y})",
                external_reference=line["reference"],
                batch=batch,
                audit=False,
            )

    def revalidate(self, batch):
        problems = []
        totals = defaultdict(lambda: 0)
        entries = list(batch.transactions.filter(status=TransactionStatus.PENDING).select_related("loan", "member"))
        for entry in entries:
            totals[entry.loan_id] += entry.amount
        checked = set()
        for entry in entries:
            loan = entry.loan
            if loan.pk in checked:
                continue
            checked.add(loan.pk)
            if loan.status not in Loan.RUNNING_STATUSES:
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"{loan.reference} is now {loan.get_status_display().lower()}."]})
                continue
            other = _payroll_months({loan.member_id: [loan]}, exclude_batch=batch)
            if any(e.period and (loan.pk, e.period) in other for e in entries if e.loan_id == loan.pk):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"Another payroll batch has since recorded {loan.reference} for the same month."]})
                continue
            available = repayable(loan, exclude_batch=batch)
            if totals[loan.pk] > available:
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": [f"Only ₦{available:,.2f} is now owed on {loan.reference}."]})
        return problems

    def template(self):
        return build_template(
            "Loan repayments",
            [
                ("Membership number", False, "Or use Staff number / IPPIS number instead."),
                ("Staff number", False, ""),
                ("IPPIS number", False, ""),
                ("Name", False, "For your own checking; ignored by the system."),
                ("Loan reference", False, "Needed only if the member has more than one running loan."),
                ("Amount", True, "Naira deducted, e.g. 25000"),
                ("Month", False, "e.g. 2026-03. Blank = the month chosen for the batch."),
                ("Reference", False, "Payroll reference."),
            ],
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "", 25000, "2026-03", "PAYROLL-MAR26"]],
            notes=["A repayment can never exceed what is still owed. The batch needs a second officer's approval."],
        )
