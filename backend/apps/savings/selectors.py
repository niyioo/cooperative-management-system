from django.db.models import Sum
from django.utils import timezone

from apps.ledger.choices import TransactionType
from apps.ledger.models import Transaction
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO, net_by

from .models import ProductKind, SavingsAccount
from .rules import cycle_months


def member_savings_position(member):
    """
    Savings grouped as the member portal shows them (BR-03):
    Christmas (cycle) savings kept separate from other savings, plus the total.
    """
    balances = net_by("savings_account", member=member)
    accounts = SavingsAccount.objects.filter(member=member).select_related("product", "cycle")
    current_year = timezone.localdate().year

    cycle, other = [], []
    for account in accounts:
        entry = {
            "id": str(account.pk),
            "account_number": account.account_number,
            "product": account.product.name,
            "product_code": account.product.code,
            "year": account.cycle.year if account.cycle_id else None,
            "status": account.status,
            "balance": balances.get(account.pk, ZERO),
        }
        (cycle if account.product.kind == ProductKind.CYCLE else other).append(entry)

    cycle.sort(key=lambda a: (a["year"] or 0), reverse=True)
    current_cycle = [a for a in cycle if a["year"] == current_year]
    other_total = sum((a["balance"] for a in other), ZERO)
    return {
        "christmas": {
            "year": current_year,
            "balance": sum((a["balance"] for a in current_cycle), ZERO),
            "accounts": cycle,
        },
        "other": {"balance": other_total, "accounts": other},
        "total": sum((a["balance"] for a in cycle + other), ZERO),
    }


def cycle_grid(cycle, accounts):
    """
    The Christmas Savings grid: one row per account, one column per month of the
    cycle (January–October for EMDI), plus the total and the expected amount.
    Only posted entries count; a reversal nets out in the month it belongs to.
    """
    months = cycle_months(cycle)
    month_keys = [m.strftime("%Y-%m") for m in months]
    accounts = list(accounts)
    cells = {}
    rows = (
        Transaction.objects.posted()
        .filter(savings_account__in=[a.pk for a in accounts])
        .values("savings_account", "period", "txn_type")
        .annotate(net=Sum(SIGNED_AMOUNT))
    )
    for row in rows:
        if row["txn_type"] == TransactionType.SAVINGS_CYCLE_PAYOUT:
            key = "paid_out"
        else:
            month = row["period"].strftime("%Y-%m") if row["period"] else None
            key = month if month in month_keys else "other"
        account_cells = cells.setdefault(row["savings_account"], {})
        account_cells[key] = account_cells.get(key, ZERO) + row["net"]

    column_totals = {k: ZERO for k in month_keys + ["other"]}
    paid_out_total = ZERO
    result = []
    for account in accounts:
        by_month = cells.get(account.pk, {})
        expected_monthly = account.elected_monthly_amount or cycle.expected_monthly_contribution
        entry = {
            "account_id": str(account.pk),
            "account_number": account.account_number,
            "member_id": str(account.member_id),
            "membership_number": account.member.membership_number,
            "member_name": account.member.full_name,
            "months": {k: by_month.get(k, ZERO) for k in month_keys},
            "other": by_month.get("other", ZERO),
            "total": sum((v for k, v in by_month.items() if k != "paid_out"), ZERO),
            "paid_out": -by_month.get("paid_out", ZERO),
            "expected_monthly": expected_monthly,
            "expected_total": expected_monthly * len(months),
        }
        for k in month_keys:
            column_totals[k] += entry["months"][k]
        column_totals["other"] += entry["other"]
        paid_out_total += entry["paid_out"]
        result.append(entry)
    return {
        "cycle": {"id": str(cycle.pk), "name": str(cycle), "status": cycle.status},
        "months": month_keys,
        "rows": result,
        "totals": {**column_totals, "total": sum(column_totals.values(), ZERO), "paid_out": paid_out_total},
    }
