"""
Dividend basis calculation (ARCHITECTURE.md §6.5).

For each member, the balances of their eligible accounts (investment products,
plus any savings products the cycle includes) are summed at each month end of
the financial year up to the cutoff date:

  CLOSING_BALANCE          balance at the cutoff date
  AVERAGE_MONTHLY_BALANCE  mean of the month-end balances (rewards money held all year)
  MINIMUM_BALANCE          lowest month-end balance

Only posted ledger entries count. Members whose membership is CLOSED are
excluded: they were settled in full when they left.
"""
import calendar
from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q, Sum

from apps.ledger.models import Transaction
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO
from apps.members.models import MemberStatus

KOBO = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(KOBO, rounding=ROUND_HALF_UP)


def measurement_points(year, cutoff):
    """Month ends from January to the cutoff; a mid-month cutoff is itself the last point."""
    points = []
    for month in range(1, 13):
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        if date(year, month, 1) > cutoff:
            break
        points.append(min(month_end, cutoff))
    return points


def member_bases(cycle):
    """{member_id: {"basis": Decimal, "balances": {"2026-01": Decimal, …}}} for members with a positive basis."""
    investment_products = list(cycle.eligible_investment_products.values_list("pk", flat=True))
    savings_products = list(cycle.eligible_savings_products.values_list("pk", flat=True))
    points = measurement_points(cycle.financial_year, cycle.cutoff_date)

    rows = (
        Transaction.objects.posted()
        .filter(value_date__lte=cycle.cutoff_date)
        .filter(Q(investment_account__product__in=investment_products) | Q(savings_account__product__in=savings_products))
        .exclude(member__status=MemberStatus.CLOSED)
        .values("member", "value_date")
        .annotate(net=Sum(SIGNED_AMOUNT))
        .order_by("member", "value_date")
    )
    movements = defaultdict(list)  # member -> [(date, running balance)]
    for row in rows:
        history = movements[row["member"]]
        running = (history[-1][1] if history else ZERO) + row["net"]
        history.append((row["value_date"], running))

    results = {}
    for member_id, history in movements.items():
        dates = [d for d, _ in history]
        balances = []
        for point in points:
            index = bisect_right(dates, point)
            balances.append(history[index - 1][1] if index else ZERO)
        if cycle.basis == cycle.Basis.CLOSING_BALANCE:
            basis = balances[-1]
        elif cycle.basis == cycle.Basis.MINIMUM_BALANCE:
            basis = min(balances)
        else:
            basis = money(sum(balances, ZERO) / len(balances))
        basis = max(basis, ZERO)
        if basis > 0:
            results[member_id] = {
                "basis": basis,
                "balances": {p.strftime("%Y-%m"): b for p, b in zip(points, balances)},
            }
    return results


def dividend_amounts(basis, rate, withholding_rate):
    gross = money(basis * Decimal(rate) / 100)
    withholding = money(gross * Decimal(withholding_rate) / 100)
    return gross, withholding, gross - withholding
