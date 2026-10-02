"""
The cooperative's reports. Each one is a selector over existing data; nothing
here writes to the database. Balances come from the ledger (D1), so "as at"
means the signed sum of posted entries with value_date on or before that day.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.accounts.models import is_placeholder_email
from apps.accounts.perms import P
from apps.common.fields import MoneyField
from apps.closures.models import AccountClosureRequest
from apps.dividends.models import DividendCalculationRun, DividendCycle, MemberDividend
from apps.investments.models import InvestmentAccount
from apps.ledger.choices import EntrySide, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO, net_by
from apps.ledger.statements import statement_rows
from apps.loans.models import Loan, LoanRepayment
from apps.loans.selectors import overdue_loans
from apps.members.models import Member, MemberStatus
from apps.savings.models import ProductKind, SavingsAccount, SavingsCycle
from apps.savings.rules import cycle_months
from apps.savings.selectors import cycle_grid
from apps.savings.statutory import arrears_rows

from .engine import DATE, INT, MONEY, PERCENT, Column, Report, register

POSTED = (TransactionStatus.POSTED, TransactionStatus.REVERSED)


def _by_department(queryset, f, path="member__department_id"):
    return queryset.filter(**{path: f["department"]}) if f.get("department") else queryset


def _member_cols():
    return [Column("membership_number", "Member no."), Column("member", "Member")]


def _member_vals(member):
    return {"membership_number": member.membership_number, "member": member.full_name}


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

@register
class MembersReport(Report):
    key = "members"
    title = "Membership register"
    description = "Every member with department, contact details and status. Filter by when they joined."
    module = "Members"
    permission = P.VIEW_MEMBER
    filters = ("status", "department", "date_from", "date_to")
    status_choices = MemberStatus.choices
    columns = [
        *_member_cols(), Column("staff_number", "Staff no."), Column("department", "Department"), Column("phone", "Phone"),
        Column("email", "Email"), Column("date_joined", "Joined", DATE), Column("status", "Status"),
    ]

    def rows(self, f):
        qs = _by_department(Member.objects.select_related("department", "user"), f, "department_id")
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        if f.get("date_from"):
            qs = qs.filter(date_joined__gte=f["date_from"])
        if f.get("date_to"):
            qs = qs.filter(date_joined__lte=f["date_to"])
        for m in qs.order_by("membership_number"):
            yield {
                **_member_vals(m), "staff_number": m.staff_number or "", "department": m.department.name if m.department_id else "",
                "phone": m.phone, "email": "" if is_placeholder_email(m.user.email) else m.user.email,
                "date_joined": m.date_joined, "status": m.get_status_display(),
            }

    def summary(self, rows, f):
        counts = defaultdict(int)
        for r in rows:
            counts[r["status"]] += 1
        return [("Members", len(rows), INT)] + [(status, n, INT) for status, n in sorted(counts.items())]


# ---------------------------------------------------------------------------
# Savings
# ---------------------------------------------------------------------------

@register
class SavingsReport(Report):
    key = "savings"
    title = "Savings balances"
    description = "Every savings account with its balance on a chosen date, Christmas Savings shown separately from other savings."
    module = "Savings"
    permission = P.VIEW_SAVINGS
    filters = ("as_at", "product", "department", "status")
    status_choices = SavingsAccount.Status.choices
    columns = [
        *_member_cols(), Column("account_number", "Account"), Column("product", "Product"), Column("kind", "Type"),
        Column("status", "Status"), Column("balance", "Balance", MONEY, total=True),
    ]

    def rows(self, f):
        qs = _by_department(SavingsAccount.objects.select_related("member", "product", "cycle"), f)
        if f.get("product"):
            qs = qs.filter(product_id=f["product"])
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        balances = net_by("savings_account", value_date__lte=f["as_at"])
        for a in qs.order_by("member__membership_number", "product__display_order", "account_number"):
            yield {
                **_member_vals(a.member), "account_number": a.account_number,
                "product": f"{a.product.name} {a.cycle.year}" if a.cycle_id else a.product.name,
                "kind": "Christmas / cycle" if a.product.kind == ProductKind.CYCLE else "Regular",
                "status": a.get_status_display(), "balance": balances.get(a.pk, ZERO),
            }

    def summary(self, rows, f):
        cycle = sum((r["balance"] for r in rows if r["kind"] != "Regular"), ZERO)
        regular = sum((r["balance"] for r in rows if r["kind"] == "Regular"), ZERO)
        return [("Christmas / cycle savings", cycle, MONEY), ("Other savings", regular, MONEY), ("Total savings", cycle + regular, MONEY)]


@register
class ContributionArrearsReport(Report):
    key = "contribution-arrears"
    title = "Monthly contribution arrears"
    description = (
        "Members whose posted monthly contributions are below what they should have paid since tracking began "
        "(BR-29), largest arrears first."
    )
    module = "Savings"
    permission = P.VIEW_SAVINGS
    filters = ("department",)
    columns = [
        *_member_cols(), Column("staff_number", "Staff no."), Column("department", "Department"), Column("phone", "Phone"),
        Column("monthly", "Monthly amount", MONEY), Column("tracked_from", "Tracked from", DATE),
        Column("expected", "Expected", MONEY, total=True), Column("paid", "Paid", MONEY, total=True),
        Column("arrears", "Arrears", MONEY, total=True), Column("months_behind", "Months behind", INT),
    ]

    def rows(self, f):
        for account, p in arrears_rows(f.get("department")):
            m = account.member
            yield {
                **_member_vals(m), "staff_number": m.staff_number or "", "department": m.department.name if m.department_id else "",
                "phone": m.phone, "monthly": p["amount"], "tracked_from": p["tracked_from"], "expected": p["expected_total"],
                "paid": p["paid_total"], "arrears": p["arrears"], "months_behind": p["months_behind"],
            }

    def summary(self, rows, f):
        return [("Members in arrears", len(rows), INT), ("Total arrears", sum((r["arrears"] for r in rows), ZERO), MONEY)]


@register
class ChristmasSavingsReport(Report):
    key = "christmas-savings"
    title = "Christmas Savings grid"
    description = "Contributions per member per month for a year's Christmas Savings cycle (January to October), with totals and payouts."
    module = "Savings"
    permission = P.VIEW_SAVINGS
    filters = ("year", "department")

    def _cycle(self, f):
        return (
            SavingsCycle.objects.filter(year=f["year"], product__kind=ProductKind.CYCLE)
            .select_related("product").order_by("product__display_order").first()
        )

    def get_columns(self, f):
        cycle = self._cycle(f)
        months = []
        if cycle:
            months = [Column(m.strftime("%Y-%m"), m.strftime("%b"), MONEY, total=True) for m in cycle_months(cycle)]
        return [*_member_cols(), *months, Column("other", "Other", MONEY, total=True), Column("total", "Total", MONEY, total=True),
                Column("expected_total", "Expected", MONEY, total=True), Column("paid_out", "Paid out", MONEY, total=True)]

    def rows(self, f):
        cycle = self._cycle(f)
        if cycle is None:
            return []
        accounts = _by_department(cycle.accounts.select_related("member"), f).order_by("member__last_name", "member__first_name")
        grid = cycle_grid(cycle, accounts)
        return [
            {"membership_number": r["membership_number"], "member": r["member_name"], **r["months"], "other": r["other"],
             "total": r["total"], "expected_total": r["expected_total"], "paid_out": r["paid_out"]}
            for r in grid["rows"]
        ]

    def summary(self, rows, f):
        cycle = self._cycle(f)
        if cycle is None:
            return [("Cycle", f"No Christmas Savings cycle for {f['year']}", "text")]
        total = sum((r["total"] for r in rows), ZERO)
        return [("Cycle", str(cycle), "text"), ("Status", cycle.get_status_display(), "text"), ("Members", len(rows), INT),
                ("Total saved", total, MONEY)]


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

@register
class LoansReport(Report):
    key = "loans"
    title = "Loan register"
    description = "Loans with terms and the outstanding balance on a chosen date. Filter by disbursement date, product or status."
    module = "Loans"
    permission = P.VIEW_LOANS
    filters = ("as_at", "status", "product", "department", "date_from", "date_to")
    status_choices = Loan.Status.choices
    columns = [
        Column("reference", "Loan"), *_member_cols(), Column("product", "Product"), Column("disbursed_on", "Disbursed", DATE),
        Column("term_months", "Term (months)", INT), Column("interest_rate", "Rate", PERCENT),
        Column("principal", "Principal", MONEY, total=True), Column("total_interest", "Interest", MONEY, total=True),
        Column("outstanding", "Outstanding", MONEY, total=True), Column("maturity_date", "Matures", DATE), Column("status", "Status"),
    ]

    def rows(self, f):
        qs = _by_department(Loan.objects.select_related("member", "product").exclude(status=Loan.Status.CANCELLED), f)
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        if f.get("product"):
            qs = qs.filter(product_id=f["product"])
        if f.get("date_from"):
            qs = qs.filter(disbursed_on__gte=f["date_from"])
        if f.get("date_to"):
            qs = qs.filter(disbursed_on__lte=f["date_to"])
        nets = net_by("loan", value_date__lte=f["as_at"])
        for loan in qs.order_by("-disbursed_on", "reference"):
            yield {
                "reference": loan.reference, **_member_vals(loan.member), "product": loan.product.name,
                "disbursed_on": loan.disbursed_on, "term_months": loan.term_months, "interest_rate": loan.interest_rate,
                "principal": loan.principal, "total_interest": loan.total_interest, "outstanding": -nets.get(loan.pk, ZERO),
                "maturity_date": loan.maturity_date, "status": loan.get_status_display(),
            }

    def summary(self, rows, f):
        return [("Loans", len(rows), INT), ("Principal", sum((r["principal"] for r in rows), ZERO), MONEY),
                ("Outstanding", sum((r["outstanding"] for r in rows), ZERO), MONEY)]


@register
class LoanRepaymentsReport(Report):
    key = "loan-repayments"
    title = "Loan repayments"
    description = "Posted loan repayments in a period, split into principal, interest and penalty."
    module = "Loans"
    permission = P.VIEW_LOANS
    filters = ("date_from", "date_to", "product", "department", "member")
    columns = [
        Column("value_date", "Date", DATE), Column("reference", "Reference"), *_member_cols(), Column("loan", "Loan"),
        Column("amount", "Amount", MONEY, total=True), Column("principal", "Principal", MONEY, total=True),
        Column("interest", "Interest", MONEY, total=True), Column("penalty", "Penalty", MONEY, total=True),
    ]

    def rows(self, f):
        qs = LoanRepayment.objects.select_related("transaction", "loan__member").filter(transaction__status=TransactionStatus.POSTED)
        qs = _by_department(qs, f, "loan__member__department_id")
        if f.get("product"):
            qs = qs.filter(loan__product_id=f["product"])
        if f.get("member"):
            qs = qs.filter(loan__member_id=f["member"])
        if f.get("date_from"):
            qs = qs.filter(transaction__value_date__gte=f["date_from"])
        if f.get("date_to"):
            qs = qs.filter(transaction__value_date__lte=f["date_to"])
        for r in qs.order_by("transaction__value_date", "transaction__reference"):
            yield {
                "value_date": r.transaction.value_date, "reference": r.transaction.reference, **_member_vals(r.loan.member),
                "loan": r.loan.reference, "amount": r.transaction.amount, "principal": r.principal_component,
                "interest": r.interest_component, "penalty": r.penalty_component,
            }

    def summary(self, rows, f):
        return [("Repayments", len(rows), INT), ("Collected", sum((r["amount"] for r in rows), ZERO), MONEY)]


@register
class OverdueLoansReport(Report):
    key = "overdue-loans"
    title = "Overdue loans"
    description = "Running loans with instalments past due (after the grace period), worst first, with contact numbers for follow-up."
    module = "Loans"
    permission = P.VIEW_LOANS
    filters = ("product", "department")
    columns = [
        Column("reference", "Loan"), *_member_cols(), Column("phone", "Phone"), Column("product", "Product"),
        Column("instalments", "Overdue instalments", INT), Column("oldest_due", "Oldest due", DATE),
        Column("days_overdue", "Days overdue", INT), Column("arrears", "Arrears", MONEY, total=True),
        Column("outstanding", "Outstanding", MONEY, total=True),
    ]

    def rows(self, f):
        for o in overdue_loans():
            loan = o["loan"]
            if f.get("product") and str(loan.product_id) != str(f["product"]):
                continue
            if f.get("department") and str(loan.member.department_id) != str(f["department"]):
                continue
            yield {
                "reference": loan.reference, **_member_vals(loan.member), "phone": loan.member.phone, "product": loan.product.name,
                "instalments": o["arrears"]["instalments"], "oldest_due": o["arrears"]["oldest_due_date"],
                "days_overdue": o["arrears"]["days_overdue"], "arrears": o["arrears"]["amount"], "outstanding": o["outstanding"],
            }

    def summary(self, rows, f):
        return [("Overdue loans", len(rows), INT), ("Total arrears", sum((r["arrears"] for r in rows), ZERO), MONEY)]


# ---------------------------------------------------------------------------
# Investments and dividends
# ---------------------------------------------------------------------------

@register
class InvestmentsReport(Report):
    key = "investments"
    title = "Investment balances"
    description = "Every investment account with its principal on a chosen date."
    module = "Investments"
    permission = P.VIEW_INVESTMENTS
    filters = ("as_at", "product", "department", "status")
    status_choices = InvestmentAccount.Status.choices
    columns = [
        *_member_cols(), Column("account_number", "Account"), Column("product", "Product"), Column("opened_on", "Opened", DATE),
        Column("status", "Status"), Column("principal", "Principal", MONEY, total=True),
    ]

    def rows(self, f):
        qs = _by_department(InvestmentAccount.objects.select_related("member", "product"), f)
        if f.get("product"):
            qs = qs.filter(product_id=f["product"])
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        balances = net_by("investment_account", value_date__lte=f["as_at"])
        for a in qs.order_by("member__membership_number", "account_number"):
            yield {**_member_vals(a.member), "account_number": a.account_number, "product": a.product.name,
                   "opened_on": a.opened_on, "status": a.get_status_display(), "principal": balances.get(a.pk, ZERO)}

    def summary(self, rows, f):
        return [("Accounts", len(rows), INT), ("Total principal", sum((r["principal"] for r in rows), ZERO), MONEY)]


@register
class DividendsReport(Report):
    key = "dividends"
    title = "Dividends"
    description = "Each member's dividend for a financial year: basis, gross, withholding, net and payment status."
    module = "Dividends"
    permission = P.VIEW_DIVIDENDS
    filters = ("year", "department", "status")
    status_choices = MemberDividend.Status.choices
    columns = [
        *_member_cols(), Column("basis", "Basis", MONEY, total=True), Column("rate", "Rate", PERCENT),
        Column("gross", "Gross", MONEY, total=True), Column("withholding", "Withholding", MONEY, total=True),
        Column("net", "Net", MONEY, total=True), Column("status", "Status"), Column("paid_at", "Paid", DATE),
    ]

    def _run(self, f):
        cycle = DividendCycle.objects.filter(financial_year=f["year"]).exclude(status=DividendCycle.Status.CANCELLED).first()
        if cycle is None:
            return None, None
        run = cycle.approved_run or cycle.runs.exclude(status=DividendCalculationRun.Status.SUPERSEDED).order_by("-run_number").first()
        return cycle, run

    def rows(self, f):
        cycle, run = self._run(f)
        if run is None:
            return []
        qs = _by_department(MemberDividend.objects.filter(run=run).select_related("member"), f)
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        return [
            {**_member_vals(d.member), "basis": d.basis_amount, "rate": d.rate, "gross": d.gross_amount,
             "withholding": d.withholding_amount, "net": d.net_amount, "status": d.get_status_display(),
             "paid_at": d.paid_at.date() if d.paid_at else None}
            for d in qs.order_by("member__membership_number")
        ]

    def summary(self, rows, f):
        cycle, run = self._run(f)
        if cycle is None:
            return [("Cycle", f"No dividend cycle for {f['year']}", "text")]
        return [("Cycle", f"{cycle.reference} ({cycle.get_status_display()})", "text"), ("Rate", cycle.rate, PERCENT),
                ("Members", len(rows), INT), ("Net dividends", sum((r["net"] for r in rows), ZERO), MONEY)]


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def _account_label(t):
    if t.savings_account_id:
        acct = t.savings_account
        return f"{acct.product.name} {acct.cycle.year}" if acct.cycle_id else acct.product.name
    if t.loan_id:
        return f"Loan {t.loan.reference}"
    if t.investment_account_id:
        return t.investment_account.product.name
    return "Paid outside the cooperative"


@register
class TransactionsReport(Report):
    key = "transactions"
    title = "Transactions"
    description = "Posted ledger entries in a period, including reversals, with credit and debit totals."
    module = "Ledger"
    permission = P.VIEW_ALL_TRANSACTIONS
    filters = ("date_from", "date_to", "txn_type", "member", "department")
    txn_type_choices = TransactionType.choices
    columns = [
        Column("value_date", "Date", DATE), Column("reference", "Reference"), *_member_cols(), Column("type", "Type"),
        Column("account", "Account"), Column("credit", "Credit", MONEY, total=True), Column("debit", "Debit", MONEY, total=True),
        Column("status", "Status"),
    ]

    def rows(self, f):
        qs = Transaction.objects.filter(status__in=POSTED).select_related(
            "member", "savings_account__product", "savings_account__cycle", "loan", "investment_account__product"
        )
        qs = _by_department(qs, f)
        for name, lookup in (("date_from", "value_date__gte"), ("date_to", "value_date__lte"), ("txn_type", "txn_type"), ("member", "member_id")):
            if f.get(name):
                qs = qs.filter(**{lookup: f[name]})
        for t in qs.order_by("value_date", "created_at"):
            credit = t.entry_side == EntrySide.CREDIT
            yield {
                "value_date": t.value_date, "reference": t.reference, **_member_vals(t.member), "type": t.get_txn_type_display(),
                "account": _account_label(t), "credit": t.amount if credit else None, "debit": None if credit else t.amount,
                "status": t.get_status_display(),
            }

    def summary(self, rows, f):
        credits = sum((r["credit"] for r in rows if r["credit"]), ZERO)
        debits = sum((r["debit"] for r in rows if r["debit"]), ZERO)
        return [("Entries", len(rows), INT), ("Credits", credits, MONEY), ("Debits", debits, MONEY)]


@register
class FinancialSummaryReport(Report):
    key = "financial-summary"
    title = "Financial summary"
    description = "Activity by transaction type for a period, and the cooperative's savings, loan and investment positions at its end."
    module = "Ledger"
    permission = P.VIEW_ALL_TRANSACTIONS
    filters = ("date_from", "date_to")
    landscape = False
    columns = [
        Column("type", "Transaction type"), Column("count", "Entries", INT, total=True), Column("credits", "Credits", MONEY, total=True),
        Column("debits", "Debits", MONEY, total=True), Column("net", "Net", MONEY, total=True),
    ]

    def rows(self, f):
        qs = Transaction.objects.filter(status__in=POSTED)
        if f.get("date_from"):
            qs = qs.filter(value_date__gte=f["date_from"])
        if f.get("date_to"):
            qs = qs.filter(value_date__lte=f["date_to"])
        rows = (
            qs.order_by().values("txn_type").annotate(
                count=Count("id"),
                credits=Coalesce(Sum("amount", filter=Q(entry_side=EntrySide.CREDIT)), Value(ZERO), output_field=MoneyField()),
                debits=Coalesce(Sum("amount", filter=Q(entry_side=EntrySide.DEBIT)), Value(ZERO), output_field=MoneyField()),
            ).order_by("txn_type")
        )
        return [
            {"type": TransactionType(r["txn_type"]).label, "count": r["count"], "credits": r["credits"], "debits": r["debits"],
             "net": r["credits"] - r["debits"]}
            for r in rows
        ]

    def summary(self, rows, f):
        posted = Transaction.objects.posted()
        if f.get("date_to"):
            posted = posted.filter(value_date__lte=f["date_to"])

        def net(qs):
            return qs.aggregate(total=Sum(SIGNED_AMOUNT))["total"] or ZERO

        savings = posted.filter(savings_account__isnull=False)
        cycle = net(savings.filter(savings_account__product__kind=ProductKind.CYCLE))
        regular = net(savings.filter(savings_account__product__kind=ProductKind.REGULAR))
        loans = -net(posted.filter(loan__isnull=False))
        investments = net(posted.filter(investment_account__isnull=False))
        label = f"at {f['date_to']:%d %b %Y}" if f.get("date_to") else "today"
        return [
            (f"Christmas / cycle savings {label}", cycle, MONEY), (f"Other savings {label}", regular, MONEY),
            (f"Loans outstanding {label}", loans, MONEY), (f"Investments {label}", investments, MONEY),
        ]


@register
class MemberStatementReport(Report):
    key = "member-statement"
    title = "Member statement"
    description = "One member's posted transactions in a period, as on the statement members download from the portal."
    module = "Members"
    permission = P.VIEW_ALL_TRANSACTIONS
    filters = ("member", "date_from", "date_to")
    required_filters = ("member",)
    columns = [
        Column("date", "Date", DATE), Column("reference", "Reference"), Column("description", "Description"),
        Column("account", "Account"), Column("credit", "Credit", MONEY, total=True), Column("debit", "Debit", MONEY, total=True),
        Column("status", "Status"),
    ]

    def _member(self, f):
        return Member.objects.filter(pk=f["member"]).first()

    def rows(self, f):
        member = self._member(f)
        if member is None:
            return []
        return [{k: r[k] for k in ("date", "reference", "description", "account", "credit", "debit", "status")}
                for r in statement_rows(member, f.get("date_from"), f.get("date_to"))]

    def summary(self, rows, f):
        member = self._member(f)
        if member is None:
            return [("Member", "Not found", "text")]
        credits = sum((r["credit"] for r in rows if r["credit"]), ZERO)
        debits = sum((r["debit"] for r in rows if r["debit"]), ZERO)
        return [("Member", f"{member.full_name} ({member.membership_number})", "text"), ("Credits", credits, MONEY), ("Debits", debits, MONEY)]


# ---------------------------------------------------------------------------
# Account closures
# ---------------------------------------------------------------------------

@register
class AccountClosuresReport(Report):
    key = "account-closures"
    title = "Account closures"
    description = "Closure requests submitted in a period, with decisions and the settlement figure approved."
    module = "Members"
    permission = P.VIEW_CLOSURE_REQUESTS
    filters = ("status", "date_from", "date_to", "department")
    status_choices = AccountClosureRequest.Status.choices
    columns = [
        Column("reference", "Request"), *_member_cols(), Column("reason", "Reason"), Column("submitted", "Submitted", DATE),
        Column("status", "Status"), Column("decided_by", "Decided by"), Column("net_payable", "Net payable", MONEY, total=True),
        Column("closed_at", "Closed", DATE),
    ]

    def rows(self, f):
        qs = _by_department(AccountClosureRequest.objects.select_related("member", "decided_by"), f)
        if f.get("status"):
            qs = qs.filter(status=f["status"])
        if f.get("date_from"):
            qs = qs.filter(created_at__date__gte=f["date_from"])
        if f.get("date_to"):
            qs = qs.filter(created_at__date__lte=f["date_to"])
        for r in qs.order_by("-created_at"):
            statement = r.settlement_statement or {}
            yield {
                "reference": r.reference, **_member_vals(r.member), "reason": r.get_reason_category_display(),
                "submitted": r.created_at.date(), "status": r.get_status_display(),
                "decided_by": r.decided_by.full_name if r.decided_by_id else "",
                "net_payable": Decimal(statement["net_payable"]) if statement.get("net_payable") else None,
                "closed_at": r.closed_at.date() if r.closed_at else None,
            }

    def summary(self, rows, f):
        counts = defaultdict(int)
        for r in rows:
            counts[r["status"]] += 1
        return [("Requests", len(rows), INT)] + [(s, n, INT) for s, n in sorted(counts.items())]
