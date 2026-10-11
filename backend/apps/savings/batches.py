"""
Savings batch types (ARCHITECTURE.md D5):

  CONTRIBUTIONS      monthly payroll deduction schedules
  OPENING_BALANCES   go-live balances for regular savings
  CYCLE_PAYOUTS      end-of-cycle Christmas Savings payout (built by the system)
"""
from django.utils import timezone

from apps.accounts.perms import P
from apps.common.spreadsheets import SpreadsheetError, build_template, cell_text, parse_amount, parse_period
from apps.ledger import services as ledger
from apps.ledger.batches import BatchHandler
from apps.ledger.choices import BatchType, TransactionStatus, TransactionType
from apps.ledger.models import Transaction
from apps.members.batch_rows import IDENTIFIER_LABELS, MemberRowsMixin, batch_report
from apps.members.models import MemberStatus
from apps.notifications import services as notifications

from .models import ProductKind, SavingsAccount, SavingsCycle, SavingsProduct
from .rules import contribution_problems, month_start, resolve_account

def _products_by_code():
    return {p.code: p for p in SavingsProduct.objects.all()}


class ContributionBatchHandler(MemberRowsMixin, BatchHandler):
    batch_type = BatchType.CONTRIBUTIONS
    permissions = (P.POST_SAVINGS_CONTRIBUTION,)
    file_options = ("product", "period")
    columns = {
        **IDENTIFIER_LABELS,
        "name": "Name",
        "product": "Product code",
        "amount": "Amount",
        "period": "Month",
        "reference": "Reference",
    }
    required = {"amount": "Amount"}

    def validate_file(self, header, data, options):
        rows, unknown, members = self._read(header, data)
        products = _products_by_code()
        default_code = (options.get("product") or "").strip().upper()
        default_product = products.get(default_code) if default_code else None
        if default_code and default_product is None:
            raise SpreadsheetError(f"Unknown product code {default_code}.")
        default_period = options.get("period")
        lines, errors, seen = [], [], {}

        for row_number, values in rows:
            row_errors = {}
            member = self._member_for(values, members, row_errors)

            code = cell_text(values.get("product")).upper()
            product = products.get(code) if code else default_product
            if code and product is None:
                row_errors["product"] = [f"Unknown product code {code}."]
            elif product is None:
                row_errors["product"] = ["Choose a product for the batch or add a Product code column."]

            try:
                amount = parse_amount(values.get("amount"))
            except ValueError as exc:
                row_errors["amount"] = [str(exc)]
                amount = None
            try:
                period = parse_period(values.get("period")) or default_period
            except ValueError as exc:
                row_errors["period"] = [str(exc)]
                period = None
            if period is None and product is not None and product.kind == ProductKind.REGULAR:
                period = month_start(timezone.localdate())

            if member and product and amount and "period" not in row_errors:
                account, problem = resolve_account(member, product, period)
                problems = [problem] if problem else contribution_problems(account, amount, period)
                if problems:
                    row_errors["amount"] = problems
                key = (member.pk, product.pk, period)
                if not product.allow_multiple_contributions_per_period and key in seen:
                    row_errors.setdefault("amount", []).append(f"Duplicate of row {seen[key]} (same member, product and month).")
                seen.setdefault(key, row_number)

            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append(
                    {"row": row_number, "member": member, "product": product, "amount": amount, "period": period,
                     "reference": cell_text(values.get("reference"))[:100]}
                )
        return lines, batch_report(len(rows), errors, unknown)

    def create_lines(self, actor, batch, lines):
        for line in lines:
            account, _ = resolve_account(line["member"], line["product"], line["period"], create=True)
            ledger.create_entry(
                actor,
                member=line["member"],
                txn_type=TransactionType.SAVINGS_CONTRIBUTION,
                amount=line["amount"],
                account=account,
                period=line["period"],
                description=f"{line['product'].name} contribution {line['period']:%b %Y}",
                external_reference=line["reference"],
                batch=batch,
                audit=False,
            )

    def revalidate(self, batch):
        problems = []
        lines = batch.transactions.filter(status=TransactionStatus.PENDING).select_related(
            "member", "savings_account__product", "savings_account__cycle", "savings_account__member"
        )
        for entry in lines:
            issues = contribution_problems(entry.savings_account, entry.amount, entry.period, ignore_batch=batch)
            if issues:
                problems.append({"reference": entry.reference, "member": entry.member.membership_number, "errors": issues})
        return problems

    def template(self):
        return build_template(
            "Contributions",
            [
                ("Membership number", False, "Or use Staff number / IPPIS number instead."),
                ("Staff number", False, ""),
                ("IPPIS number", False, ""),
                ("Name", False, "For your own checking; ignored by the system."),
                ("Product code", False, "e.g. CHRISTMAS or REGULAR. Blank = the product chosen for the batch."),
                ("Amount", True, "Naira, e.g. 5000 or 5000.50"),
                ("Month", False, "e.g. 2026-03. Blank = the month chosen for the batch."),
                ("Reference", False, "Payroll or receipt reference."),
            ],
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "CHRISTMAS", 5000, "2026-03", "PAYROLL-MAR26"]],
            notes=["One row per member, product and month. Upload, check the report, then submit for approval."],
        )


class OpeningBalanceBatchHandler(MemberRowsMixin, BatchHandler):
    """Go-live balances brought forward from the previous records (regular savings only)."""

    batch_type = BatchType.OPENING_BALANCES
    permissions = (P.POST_SAVINGS_CONTRIBUTION,)
    columns = {**IDENTIFIER_LABELS, "name": "Name", "product": "Product code", "amount": "Amount", "reference": "Reference"}
    required = {"product": "Product code", "amount": "Amount"}

    @staticmethod
    def _has_opening_balance(account, ignore_batch=None):
        if account._state.adding:  # not saved yet, so it can't have entries
            return False
        qs = Transaction.objects.filter(
            savings_account=account,
            txn_type=TransactionType.SAVINGS_OPENING_BALANCE,
            status__in=[TransactionStatus.POSTED, TransactionStatus.PENDING],
        )
        if ignore_batch is not None:
            qs = qs.exclude(batch=ignore_batch)
        return qs.exists()

    def validate_file(self, header, data, options):
        rows, unknown, members = self._read(header, data)
        products = _products_by_code()
        lines, errors, seen = [], [], {}
        for row_number, values in rows:
            row_errors = {}
            member = self._member_for(values, members, row_errors)
            code = cell_text(values.get("product")).upper()
            product = products.get(code)
            if product is None:
                row_errors["product"] = [f"Unknown product code {code or '(blank)'}."]
            elif product.kind == ProductKind.CYCLE:
                row_errors["product"] = [
                    f"Bring in {product.name} as monthly contributions (a Contributions batch per month), not an opening balance."
                ]
            try:
                amount = parse_amount(values.get("amount"))
            except ValueError as exc:
                row_errors["amount"] = [str(exc)]
                amount = None
            if member and product and "product" not in row_errors:
                if member.status == MemberStatus.CLOSED:
                    row_errors["membership_number"] = ["This membership is closed."]
                account, _ = resolve_account(member, product, None)
                if self._has_opening_balance(account):
                    row_errors["amount"] = [f"{member.full_name} already has a {product.name} opening balance."]
                key = (member.pk, product.pk)
                if key in seen:
                    row_errors.setdefault("amount", []).append(f"Duplicate of row {seen[key]}.")
                seen.setdefault(key, row_number)
            if row_errors:
                errors.append({"row": row_number, "errors": row_errors})
            else:
                lines.append({"row": row_number, "member": member, "product": product, "amount": amount,
                              "reference": cell_text(values.get("reference"))[:100]})
        return lines, batch_report(len(rows), errors, unknown)

    def create_lines(self, actor, batch, lines):
        for line in lines:
            account, _ = resolve_account(line["member"], line["product"], None, create=True)
            ledger.create_entry(
                actor,
                member=line["member"],
                txn_type=TransactionType.SAVINGS_OPENING_BALANCE,
                amount=line["amount"],
                account=account,
                description=f"{line['product'].name} balance brought forward",
                external_reference=line["reference"],
                batch=batch,
                audit=False,
            )

    def revalidate(self, batch):
        problems = []
        for entry in batch.transactions.filter(status=TransactionStatus.PENDING).select_related("member", "savings_account"):
            if self._has_opening_balance(entry.savings_account, ignore_batch=batch):
                problems.append({"reference": entry.reference, "member": entry.member.membership_number,
                                 "errors": ["An opening balance was recorded for this account after upload."]})
        return problems

    def template(self):
        return build_template(
            "Opening balances",
            [
                ("Membership number", False, "Or use Staff number / IPPIS number instead."),
                ("Staff number", False, ""),
                ("IPPIS number", False, ""),
                ("Name", False, "For your own checking; ignored by the system."),
                ("Product code", True, "A regular savings product, e.g. REGULAR."),
                ("Amount", True, "Balance brought forward at go-live."),
                ("Reference", False, "e.g. the ledger page it came from."),
            ],
            example_rows=[["EMDI/COOP/0001", "", "", "Adaeze Okafor", "REGULAR", 125000, "Ledger p.14"]],
            notes=["Each account can have one opening balance. The batch needs a second officer's approval."],
        )


class CyclePayoutBatchHandler(BatchHandler):
    """Built by prepare_cycle_payout(); no file upload."""

    batch_type = BatchType.CYCLE_PAYOUTS
    permissions = (P.POST_SAVINGS_WITHDRAWAL,)
    accepts_files = False

    @staticmethod
    def _cycle(batch):
        return SavingsCycle.objects.get(pk=batch.validation_report["cycle_id"])

    def revalidate(self, batch):
        problems = []
        for entry in batch.transactions.filter(status=TransactionStatus.PENDING).select_related("member", "savings_account"):
            balance = ledger.posted_balance(entry.savings_account)
            if balance != entry.amount:
                problems.append({
                    "reference": entry.reference,
                    "member": entry.member.membership_number,
                    "errors": [f"The balance is now ₦{balance:,.2f}, not ₦{entry.amount:,.2f}. Prepare the payout again."],
                })
        return problems

    def after_post(self, batch):
        cycle = self._cycle(batch)
        today = timezone.localdate()
        cycle.status = SavingsCycle.Status.PAID_OUT
        cycle.save(update_fields=["status", "updated_at"])
        cycle.accounts.exclude(status=SavingsAccount.Status.CLOSED).update(
            status=SavingsAccount.Status.CLOSED, closed_on=today, updated_at=timezone.now()
        )
        for entry in batch.transactions.select_related("member"):
            notifications.notify_member(
                entry.member, category=notifications.Category.SAVINGS,
                title=f"{cycle} paid out",
                body=f"Your {cycle} savings of {notifications.naira(entry.amount)} have been paid out.",
                link=notifications.link("savings"),
            )
