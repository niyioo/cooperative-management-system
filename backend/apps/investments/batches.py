"""
Investment batch types:

  INVESTMENTS                   monthly payroll investment contributions
  INVESTMENT_OPENING_BALANCES   go-live principal brought forward
"""
from apps.accounts.perms import P
from apps.common.spreadsheets import build_template, cell_text, parse_amount
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchType, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.batch_rows import IDENTIFIER_LABELS, MemberRowsMixin, batch_report

from .models import InvestmentProduct
from .services import account_problem, contribution_problems, find_or_open_account

TEMPLATE_COLUMNS = [
    ("Membership number", False, "Or use Staff number / IPPIS number instead."),
    ("Staff number", False, ""),
    ("IPPIS number", False, ""),
    ("Name", False, "For your own checking; ignored by the system."),
    ("Product code", True, "Investment product code."),
    ("Amount", True, "Naira, e.g. 20000"),
    ("Reference", False, "Payroll or ledger reference."),
]


class _InvestmentRowsHandler(MemberRowsMixin, BatchHandler):
    permissions = (P.POST_INVESTMENT_TRANSACTION,)
    columns = {**IDENTIFIER_LABELS, "name": "Name", "product": "Product code", "amount": "Amount", "reference": "Reference"}
    required = {"product": "Product code", "amount": "Amount"}
    txn_type = None

    def row_problems(self, account, amount):
        raise NotImplementedError

    def validate_file(self, header, data, options):
        rows, unknown, members = self._read(header, data)
        products = {p.code: p for p in InvestmentProduct.objects.all()}
        lines, errors, seen = [], [], {}
        for row_number, values in rows:
            row_errors = {}
            member = self._member_for(values, members, row_errors)
            code = cell_text(values.get("product")).upper()
            product = products.get(code)
            if product is None:
                row_errors["product"] = [f"Unknown investment product {code or '(blank)'}."]
            try:
                amount = parse_amount(values.get("amount"))
            except ValueError as exc:
                row_errors["amount"] = [str(exc)]
                amount = None
            if member and product and amount:
                problems = self.row_problems(find_or_open_account(member, product, create=False), amount)
                if problems:
                    row_errors["amount"] = problems
                key = (member.pk, product.pk)
                if key in seen and self.one_per_account:
                    row_errors.setdefault("amount", []).append(f"Duplicate of row {seen[key]}.")
                seen.setdefault(key, row_number)
            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append({"member": member, "product": product, "amount": amount, "reference": cell_text(values.get("reference"))[:100]})
        return lines, batch_report(len(rows), errors, unknown)

    def create_lines(self, actor, batch, lines):
        for line in lines:
            account = find_or_open_account(line["member"], line["product"], create=True)
            ledger.create_entry(
                actor,
                member=line["member"],
                txn_type=self.txn_type,
                amount=line["amount"],
                account=account,
                description=self.description(line["product"]),
                external_reference=line["reference"],
                batch=batch,
                audit=False,
            )

    def revalidate(self, batch):
        problems = []
        for entry in batch.transactions.filter(status=TransactionStatus.PENDING).select_related("member", "investment_account__product"):
            issues = self.row_problems(entry.investment_account, entry.amount, ignore_batch=batch)
            if issues:
                problems.append({"reference": entry.reference, "member": entry.member.membership_number, "errors": issues})
        return problems


class InvestmentContributionBatchHandler(_InvestmentRowsHandler):
    batch_type = BatchType.INVESTMENTS
    txn_type = TransactionType.INVESTMENT_CONTRIBUTION
    one_per_account = False

    def row_problems(self, account, amount, ignore_batch=None):
        return contribution_problems(account, amount)

    def description(self, product):
        return f"{product.name} contribution"

    def template(self):
        return build_template(
            "Investment contributions",
            TEMPLATE_COLUMNS,
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "SHARES", 20000, "PAYROLL-MAR26"]],
            notes=["Accounts are opened automatically on a member's first contribution to a product."],
        )


class InvestmentOpeningBalanceBatchHandler(_InvestmentRowsHandler):
    batch_type = BatchType.INVESTMENT_OPENING_BALANCES
    txn_type = TransactionType.INVESTMENT_OPENING_BALANCE
    one_per_account = True

    def row_problems(self, account, amount, ignore_batch=None):
        problem = account_problem(account.member, account.product)
        if problem:
            return [problem]
        if not account._state.adding:
            existing = Transaction.objects.filter(
                investment_account=account,
                txn_type=TransactionType.INVESTMENT_OPENING_BALANCE,
                status__in=[TransactionStatus.POSTED, TransactionStatus.PENDING],
            )
            if ignore_batch is not None:
                existing = existing.exclude(batch=ignore_batch)
            if existing.exists():
                return [f"{account.member.full_name} already has a {account.product.name} opening balance."]
        return []

    def description(self, product):
        return f"{product.name} principal brought forward"

    def template(self):
        return build_template(
            "Investment opening balances",
            TEMPLATE_COLUMNS,
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "SHARES", 250000, "Ledger p.3"]],
            notes=["Each account can have one opening balance. The batch needs a second officer's approval."],
        )
