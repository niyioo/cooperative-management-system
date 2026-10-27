"""
Loan batch types:

  LOAN_REPAYMENTS         monthly payroll loan deductions
  LOAN_OPENING_BALANCES   running loans brought forward from the previous records at go-live
"""
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
    parse_date,
    parse_period,
)
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchType, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.lookup import IDENTIFIER_FIELDS, members_by_identifier

from apps.members.batch_rows import IDENTIFIER_LABELS, MemberRowsMixin, batch_report
from apps.members.models import MemberStatus

from .models import Loan, LoanProduct
from .services import bring_forward_loan, repayable, term_for_repayment

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


class LoanOpeningBalanceBatchHandler(MemberRowsMixin, BatchHandler):
    """Running loans taken on at go-live: what each member still owed on the balance date."""

    batch_type = BatchType.LOAN_OPENING_BALANCES
    permissions = (P.DISBURSE_LOAN,)
    file_options = ("balance_date",)
    columns = {
        **IDENTIFIER_LABELS,
        "name": "Name",
        "product": "Product code",
        "outstanding": "Outstanding",
        "monthly_repayment": "Monthly repayment",
        "term_months": "Months left",
        "balance_date": "Balance date",
        "reference": "Reference",
    }
    required = {"product": "Product code", "outstanding": "Outstanding"}

    def validate_file(self, header, data, options):
        rows, unknown, members = self._read(header, data)
        products = {p.code.upper(): p for p in LoanProduct.objects.all()}
        default_date = options.get("balance_date")
        lines, errors = [], []
        for row_number, values in rows:
            row_errors = {}
            member = self._member_for(values, members, row_errors)
            if member is not None and (not member.is_full_member or member.status == MemberStatus.CLOSED):
                row_errors["membership_number"] = [f"{member.full_name} cannot hold a loan."]
            code = cell_text(values.get("product")).upper()
            product = products.get(code)
            if product is None:
                row_errors["product"] = [f"Unknown loan product {code or '(blank)'}."]
            try:
                outstanding = parse_amount(values.get("outstanding"))
            except ValueError as exc:
                row_errors["outstanding"] = [str(exc)]
                outstanding = None
            try:
                balance_date = parse_date(values.get("balance_date")) or default_date
            except ValueError as exc:
                row_errors["balance_date"] = [str(exc)]
                balance_date = None
            if balance_date is None and "balance_date" not in row_errors:
                row_errors["balance_date"] = ["Give the date of the balance (or choose one for the batch)."]
            elif balance_date and balance_date > timezone.localdate():
                row_errors["balance_date"] = ["Cannot be in the future."]

            monthly = term = None
            if cell_text(values.get("term_months")):
                try:
                    term = int(cell_text(values.get("term_months")))
                    if not 1 <= term <= 360:
                        raise ValueError
                except ValueError:
                    row_errors["term_months"] = ["Months left must be a whole number from 1 to 360."]
            elif cell_text(values.get("monthly_repayment")):
                try:
                    monthly = parse_amount(values.get("monthly_repayment"))
                except ValueError as exc:
                    row_errors["monthly_repayment"] = [str(exc)]
            else:
                row_errors["monthly_repayment"] = ["Give the monthly repayment or the months left."]
            if monthly and product and outstanding and balance_date and not row_errors:
                term = term_for_repayment(product, outstanding, monthly, balance_date)
                if term is None:
                    row_errors["monthly_repayment"] = ["This repayment would never clear the loan on the product's interest rate."]

            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append({"member": member, "product": product, "outstanding": outstanding, "term": term,
                              "balance_date": balance_date, "reference": cell_text(values.get("reference"))[:100]})
        return lines, batch_report(len(rows), errors, unknown)

    def create_lines(self, actor, batch, lines):
        for line in lines:
            bring_forward_loan(
                actor, member=line["member"], product=line["product"], outstanding=line["outstanding"],
                balance_date=line["balance_date"], term_months=line["term"], batch=batch, external_reference=line["reference"],
            )

    def template(self):
        return build_template(
            "Loan balances",
            [
                ("Membership number", False, "Or use Staff number / IPPIS number instead."),
                ("Staff number", False, ""),
                ("IPPIS number", False, ""),
                ("Name", False, "For your own checking; ignored by the system."),
                ("Product code", True, "The loan product, e.g. REG."),
                ("Outstanding", True, "What the member still owed on the balance date."),
                ("Monthly repayment", False, "The monthly deduction (principal + interest). Or give Months left."),
                ("Months left", False, "Instead of the monthly repayment."),
                ("Balance date", False, "e.g. 2025-12-31. Blank = the date chosen for the batch."),
                ("Reference", False, "e.g. the ledger page it came from."),
            ],
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "REG", 500000, 50000, "", "2025-12-31", "Ledger p.14"]],
            notes=["Each row becomes a running loan with a repayment schedule on the product's terms. "
                   "The batch needs a second officer's approval."],
        )
