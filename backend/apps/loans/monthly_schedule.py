"""
The society's monthly spreadsheet (BR-38), uploaded as it is kept: one row per staff member with

  CTSS EMDI            deducted from salary through payroll
  TRANSFER TO ACCT     paid by hand into the society's account
  REFUND               over-deducted and paid back to the member
  then where the money goes: COOP SAVINGS, XMAS SAVINGS, PRE-RETIREMENT,
  COOP LOAN, COMMODITY, ELECTRONICS, XMAS LOAN, and TOTAL.

Money received (CTSS + transfer - refund) must equal TOTAL and the sum of the
columns it goes to. Rows find their member by membership, staff or IPPIS number
when the sheet has one, otherwise by name (the words of the name, in any order).
Each amount becomes a contribution or a loan repayment, tagged with how it was
paid; the whole sheet is one batch that a second officer approves.
"""
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.accounts.perms import P
from apps.common.spreadsheets import SpreadsheetError, build_template, cell_text, map_columns
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchType, PaymentChannel, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.batch_rows import IDENTIFIER_LABELS, batch_report, column_aliases
from apps.members.lookup import IDENTIFIER_FIELDS, members_by_identifier
from apps.members.models import Member, MemberStatus
from apps.savings.models import SavingsProduct
from apps.savings.rules import contribution_problems, month_end, resolve_account

from .models import Loan, LoanType
from .services import repayable

MONEY_IN = {"payroll": "CTSS EMDI", "transfer": "Transfer to acct", "refund": "Refund"}
SAVINGS = {"coop_savings": ("Coop savings", "REGULAR"), "xmas_savings": ("Xmas savings", "CHRISTMAS"),
           "pre_retirement": ("Pre-retirement", "PRE_RETIREMENT")}
LOANS = {"coop_loan": ("Coop loan", LoanType.STANDARD), "commodity": ("Commodity", LoanType.COMMODITY),
         "electronics": ("Electronics", LoanType.ELECTRONICS), "xmas_loan": ("Xmas loan", LoanType.CHRISTMAS)}
COLUMNS = {
    **IDENTIFIER_LABELS,
    "name": "Staff name",
    **MONEY_IN,
    **{k: label for k, (label, _) in SAVINGS.items()},
    **{k: label for k, (label, _) in LOANS.items()},
    "xmas_withdrawal": "Withdrawal from xmas savings",
    "total": "Total",
}
ALIASES = {**column_aliases(COLUMNS), "name": "name", "names": "name", "s_n": "serial", "sn": "serial"}
ZERO = Decimal("0.00")
WELL_FORMED = re.compile(r"^\d{1,3}(,\d{3})*(\.\d{1,2})?$|^\d+(\.\d{1,2})?$")


def parse_cell(value):
    """
    A money cell: blank is zero. Text must be a well-formed amount ('120,000' or '120000.50');
    a mistyped one such as '100,00.00' is refused rather than guessed.
    """
    if value in (None, ""):
        return ZERO
    if isinstance(value, (int, float, Decimal)):
        amount = Decimal(str(value))
    else:
        raw = cell_text(value).replace("₦", "").replace(" ", "")
        if not raw:
            return ZERO
        if not WELL_FORMED.match(raw):
            raise ValueError(f"'{cell_text(value)}' is not a clear amount; type it like 120000 or 120,000.00.")
        try:
            amount = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            raise ValueError(f"'{cell_text(value)}' is not an amount.") from None
    if amount < 0:
        raise ValueError("Amounts cannot be negative.")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Amounts can have at most 2 decimal places (kobo).")
    return amount.quantize(Decimal("0.01"))


def _words(text):
    """The words of a name: split on spaces and punctuation; hyphenated names count joined and split."""
    words = set()
    for part in re.split(r"[\s,./]+", (text or "").upper()):
        if not part:
            continue
        words.add(part.replace("-", ""))
        words.update(p for p in part.split("-") if p)
    return words


def _name_key(member):
    """The words that must all appear in a row's name: initials are ignored."""
    words = set()
    for part in (member.first_name, member.middle_name, member.last_name):
        for word in re.split(r"[\s,./]+", (part or "").upper()):
            if len(word.replace("-", "").replace(".", "")) > 1:
                words.add(word.replace("-", ""))
    return words


class NameIndex:
    """Finds a member from a name written in any order (BR-38)."""

    def __init__(self):
        self.members = [(m, _name_key(m)) for m in Member.objects.exclude(status=MemberStatus.CLOSED)]

    def find(self, name):
        row = _words(name)
        matches = [(m, key) for m, key in self.members if len(key) >= 2 and key <= row]
        if not matches:
            return None, f"No member called {name}. Register them first, or add a Membership number column."
        best = max(len(key) for _, key in matches)
        top = [m for m, key in matches if len(key) == best]
        if len(top) > 1:
            listed = ", ".join(f"{m.full_name} ({m.membership_number})" for m in top)
            return None, f"{name} matches more than one member ({listed}); add a Membership number column."
        return top[0], None


def channel_for(payroll, transfer):
    if payroll and transfer:
        return PaymentChannel.PAYROLL_AND_TRANSFER
    return PaymentChannel.TRANSFER if transfer else PaymentChannel.PAYROLL


def _schedule_months(loan_ids, exclude_batch=None):
    """{(loan id, month)} repayments already taken through payroll for that month (either kind of batch)."""
    entries = Transaction.objects.filter(
        loan__in=loan_ids,
        txn_type=TransactionType.LOAN_REPAYMENT,
        batch__batch_type__in=[BatchType.LOAN_REPAYMENTS, BatchType.MONTHLY_SCHEDULE],
        status__in=[TransactionStatus.POSTED, TransactionStatus.PENDING],
        period__isnull=False,
    )
    if exclude_batch is not None:
        entries = entries.exclude(batch=exclude_batch)
    return set(entries.values_list("loan_id", "period"))


class MonthlyScheduleBatchHandler(BatchHandler):
    batch_type = BatchType.MONTHLY_SCHEDULE
    permissions = (P.POST_SAVINGS_CONTRIBUTION, P.RECORD_LOAN_REPAYMENT)
    file_options = ("period",)

    def validate_file(self, header, data, options):
        period = options.get("period")
        if period is None:
            raise SpreadsheetError("Choose the month this sheet is for.")
        mapping, unknown = map_columns(header, ALIASES, {})
        keys = set(mapping.values())
        if "name" not in keys and not keys & set(IDENTIFIER_FIELDS):
            raise SpreadsheetError("The sheet needs a STAFF NAME column (or a Membership number column).")
        if not keys & ({"payroll", "transfer"}):
            raise SpreadsheetError("The sheet needs a CTSS EMDI column (salary deductions) or a TRANSFER TO ACCT column.")
        unknown = [u for u in unknown if u.upper() not in ("S/N",)]

        rows = []
        for row_number, cells in data:
            values = {key: (cells[i] if i < len(cells) else None) for i, key in mapping.items()}
            name = cell_text(values.get("name"))
            if name.upper() in ("TOTAL", "TOTALS", "GRAND TOTAL"):
                continue
            rows.append((row_number, values))
        wanted = {f: {cell_text(v.get(f)).upper() for _, v in rows if cell_text(v.get(f))} for f in IDENTIFIER_FIELDS}
        by_number = members_by_identifier(wanted)
        names = NameIndex()
        products = {p.code: p for p in SavingsProduct.objects.filter(code__in=[c for _, c in SAVINGS.values()])}

        lines, errors, seen_members = [], [], {}
        claimed = defaultdict(lambda: ZERO)
        for row_number, values in rows:
            row_errors = {}
            amounts = {}
            for key in [*MONEY_IN, *SAVINGS, *LOANS, "xmas_withdrawal", "total"]:
                try:
                    amounts[key] = parse_cell(values.get(key))
                except ValueError as exc:
                    row_errors[key] = [str(exc)]
                    amounts[key] = ZERO
            received = amounts["payroll"] + amounts["transfer"] - amounts["refund"]
            allocated = sum((amounts[k] for k in [*SAVINGS, *LOANS]), ZERO)
            if not received and not allocated and not amounts["total"] and not row_errors:
                continue  # nothing paid this month

            member = None
            identified = False
            for field in IDENTIFIER_FIELDS:
                key = cell_text(values.get(field)).upper()
                if key:
                    identified = True
                    member = by_number.get((field, key))
                    if member is None:
                        row_errors[field] = [f"No member has {IDENTIFIER_LABELS[field].lower()} {key}."]
                    break
            if not identified:
                name = cell_text(values.get("name"))
                if not name:
                    row_errors["name"] = ["Give the staff name or membership number."]
                else:
                    member, problem = names.find(name)
                    if problem:
                        row_errors["name"] = [problem]
            if member is not None:
                if member.pk in seen_members:
                    row_errors["name"] = [f"{member.full_name} is already on row {seen_members[member.pk]}."]
                seen_members.setdefault(member.pk, row_number)

            if amounts["xmas_withdrawal"]:
                row_errors["xmas_withdrawal"] = ["Withdrawals from Christmas Savings are not taken from this sheet yet; "
                                                 "record them separately and clear this cell."]
            if not row_errors.get("total") and amounts["total"] and amounts["total"] != received:
                row_errors["total"] = [f"TOTAL is ₦{amounts['total']:,.2f}, but CTSS + transfer - refund is ₦{received:,.2f}."]
            if received != allocated:
                row_errors.setdefault("total", []).append(
                    f"₦{received:,.2f} was received but ₦{allocated:,.2f} is shared out across the savings and loan columns."
                )

            entries = []
            if member is not None:
                for key, (label, code) in SAVINGS.items():
                    if not amounts[key]:
                        continue
                    product = products.get(code)
                    if product is None:
                        row_errors[key] = [f"There is no savings product {code}."]
                        continue
                    account, problem = resolve_account(member, product, period)
                    problems = [problem] if problem else contribution_problems(account, amounts[key], period)
                    if problems:
                        row_errors[key] = problems
                    else:
                        entries.append({"kind": "savings", "product": product, "amount": amounts[key]})
                running = [l for l in Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES).select_related("product")]
                already = _schedule_months([l.pk for l in running])
                for key, (label, loan_type) in LOANS.items():
                    if not amounts[key]:
                        continue
                    loans = [l for l in running if l.product.loan_type == loan_type]
                    if not loans:
                        row_errors[key] = [f"{member.full_name} has no running {label.lower()}."]
                        continue
                    if len(loans) > 1:
                        row_errors[key] = [f"{member.full_name} has {len(loans)} running {label.lower()}s; record this one by hand."]
                        continue
                    loan = loans[0]
                    if (loan.pk, period) in already:
                        row_errors[key] = [f"{loan.reference} already has a payroll repayment for {period:%B %Y}."]
                        continue
                    available = repayable(loan) - claimed[loan.pk]
                    if amounts[key] > available:
                        row_errors[key] = [f"More than the ₦{available:,.2f} still owed on {loan.reference}."]
                        continue
                    claimed[loan.pk] += amounts[key]
                    entries.append({"kind": "loan", "loan": loan, "amount": amounts[key]})

            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append({"member": member, "period": period, "entries": entries,
                              "channel": channel_for(amounts["payroll"], amounts["transfer"]),
                              "refund": amounts["refund"]})
        return lines, batch_report(len(rows), errors, unknown)

    def create_lines(self, actor, batch, lines):
        value_date = min(month_end(lines[0]["period"].year, lines[0]["period"].month), timezone.localdate()) if lines else None
        for line in lines:
            member, period, channel = line["member"], line["period"], line["channel"]
            how = PaymentChannel(channel).label.lower()
            for entry in line["entries"]:
                if entry["kind"] == "savings":
                    account, _ = resolve_account(member, entry["product"], period, create=True)
                    ledger.create_entry(actor, member=member, txn_type=TransactionType.SAVINGS_CONTRIBUTION, amount=entry["amount"],
                                        account=account, period=period, value_date=value_date, channel=channel,
                                        description=f"{entry['product'].name} {period:%b %Y} ({how})", batch=batch, audit=False)
                else:
                    loan = entry["loan"]
                    ledger.create_entry(actor, member=member, txn_type=TransactionType.LOAN_REPAYMENT, amount=entry["amount"],
                                        account=loan, period=period, value_date=value_date, channel=channel,
                                        description=f"Repayment of {loan.reference} {period:%b %Y} ({how})", batch=batch, audit=False)

    def revalidate(self, batch):
        problems = []
        entries = list(batch.transactions.filter(status=TransactionStatus.PENDING).select_related(
            "member", "loan", "savings_account__product", "savings_account__cycle", "savings_account__member"))
        totals = defaultdict(lambda: ZERO)
        for entry in entries:
            if entry.loan_id:
                totals[entry.loan_id] += entry.amount
        checked = set()
        for entry in entries:
            if entry.savings_account_id:
                issues = contribution_problems(entry.savings_account, entry.amount, entry.period, ignore_batch=batch)
            elif entry.loan_id in checked:
                continue
            else:
                checked.add(entry.loan_id)
                loan = entry.loan
                if loan.status not in Loan.RUNNING_STATUSES:
                    issues = [f"{loan.reference} is now {loan.get_status_display().lower()}."]
                elif (loan.pk, entry.period) in _schedule_months([loan.pk], exclude_batch=batch):
                    issues = [f"Another batch has since recorded {loan.reference} for {entry.period:%B %Y}."]
                elif totals[loan.pk] > repayable(loan, exclude_batch=batch):
                    issues = [f"Only ₦{repayable(loan, exclude_batch=batch):,.2f} is now owed on {loan.reference}."]
                else:
                    issues = []
            if issues:
                problems.append({"reference": entry.reference, "member": entry.member.membership_number, "errors": issues})
        return problems

    def template(self):
        return build_template(
            "Monthly schedule",
            [
                ("S/N", False, "Optional."),
                ("Staff name", True, "As on payroll; names may be in any order. Or add a Membership number column."),
                ("CTSS EMDI", False, "Deducted from salary through payroll."),
                ("Transfer to acct", False, "Paid by hand into the society's account."),
                ("Refund", False, "Over-deducted and paid back to the member."),
                ("Pre-retirement", False, "Pre-retirement Savings."),
                ("Withdrawal from xmas savings", False, "Leave blank; record withdrawals separately."),
                ("Electronics", False, "Electronics loan repayment."),
                ("Commodity", False, "Commodity loan repayment."),
                ("Xmas loan", False, "Christmas loan repayment."),
                ("Xmas savings", False, "Christmas Savings."),
                ("Coop loan", False, "Cooperative (regular) loan repayment."),
                ("Coop savings", False, "Regular Savings (at least ₦5,000)."),
                ("Total", False, "CTSS + transfer - refund; must equal the columns shared out."),
            ],
            example_rows=[[1, "OKAFOR ADAEZE CHIOMA", 80000, "", "", 20000, "", "", "", "", 20000, 30000, 10000, 80000]],
            notes=["One row per staff member for the month chosen when uploading.",
                   "Each amount becomes a contribution or loan repayment; a second officer approves the batch."],
        )
