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

A cycle may also pay its dividend in parts, as EMDI does (BR-35): one rate on
share capital, another on savings, a refund of part of the loan interest each
member paid in the year, and flat allowances (e.g. Food, Gift) for everyone who
receives a dividend. member_dividends() puts the parts together.
"""
import calendar
from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.db.models import Q, Sum

from apps.ledger.models import Transaction
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO
from apps.members.models import MembershipType, MemberStatus

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


def member_bases(cycle, investment_products=None, savings_products=None):
    """{member_id: {"basis": Decimal, "balances": {"2026-01": Decimal, …}}} for members with a positive basis."""
    if investment_products is None:
        investment_products = list(cycle.eligible_investment_products.values_list("pk", flat=True))
    if savings_products is None:
        savings_products = list(cycle.eligible_savings_products.values_list("pk", flat=True))
    points = measurement_points(cycle.financial_year, cycle.cutoff_date)

    rows = (
        Transaction.objects.posted()
        .filter(value_date__lte=cycle.cutoff_date)
        .filter(Q(investment_account__product__in=investment_products) | Q(savings_account__product__in=savings_products))
        .exclude(member__status=MemberStatus.CLOSED)
        .filter(member__membership_type=MembershipType.MEMBER)  # dividends are for members only
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


def interest_paid(cycle):
    """{member_id: loan interest paid in the financial year up to the cutoff} (posted repayments only)."""
    from apps.ledger.choices import TransactionStatus
    from apps.loans.models import LoanRepayment

    rows = (
        LoanRepayment.objects.filter(
            transaction__status=TransactionStatus.POSTED,
            transaction__value_date__gte=date(cycle.financial_year, 1, 1),
            transaction__value_date__lte=cycle.cutoff_date,
            interest_component__gt=0,
        )
        .exclude(loan__member__status=MemberStatus.CLOSED)
        .filter(loan__member__membership_type=MembershipType.MEMBER)
        .values("loan__member")
        .annotate(total=Sum("interest_component"))
    )
    return {r["loan__member"]: r["total"] for r in rows}


def has_parts(cycle):
    return cycle.savings_rate is not None or cycle.interest_refund_rate or cycle.interest_refund_pool or cycle.allowances


def member_dividends(cycle):
    """
    {member_id: {"basis", "gross", "detail"}} for everyone who receives a dividend.

    A plain cycle is the main rate on the combined basis of every eligible
    product. A cycle with parts adds them up, each part rounded on its own.
    """
    whole = (lambda v: money(Decimal(v).quantize(Decimal("1"), rounding=ROUND_DOWN))) if cycle.round_down_to_naira else money
    rate = Decimal(cycle.rate)
    if not has_parts(cycle):
        return {
            member_id: {
                "basis": info["basis"],
                "gross": whole(info["basis"] * rate / 100),
                "detail": {"month_end_balances": info["balances"], "basis": cycle.basis},
            }
            for member_id, info in member_bases(cycle).items()
        }

    separate_savings = cycle.savings_rate is not None
    main = member_bases(cycle, savings_products=[] if separate_savings else None)
    savings = member_bases(cycle, investment_products=[]) if separate_savings else {}
    interest = interest_paid(cycle) if (cycle.interest_refund_rate or cycle.interest_refund_pool) else {}
    refund_rate = Decimal(cycle.interest_refund_rate or 0)
    if cycle.interest_refund_pool:
        total_interest = sum(interest.values(), ZERO)
        refund_rate = (Decimal(cycle.interest_refund_pool) * 100 / total_interest) if total_interest else ZERO
    allowances = [(a["name"], Decimal(str(a["amount"]))) for a in cycle.allowances or []]

    results = {}
    # Allowances and the interest refund go to members with a share or savings balance, as in the society's books.
    for member_id in set(main) | set(savings):
        parts = []
        if member_id in main:
            parts.append({"part": "shares" if separate_savings else "balance", "basis": main[member_id]["basis"],
                          "rate": rate, "amount": whole(main[member_id]["basis"] * rate / 100)})
        if member_id in savings:
            parts.append({"part": "savings", "basis": savings[member_id]["basis"], "rate": Decimal(cycle.savings_rate),
                          "amount": whole(savings[member_id]["basis"] * Decimal(cycle.savings_rate) / 100)})
        if member_id in interest:
            parts.append({"part": "interest_refund", "basis": interest[member_id], "rate": refund_rate.quantize(Decimal("0.0001")),
                          "amount": whole(interest[member_id] * refund_rate / 100)})
        for name, amount in allowances:
            parts.append({"part": "allowance", "name": name, "amount": money(amount)})
        basis = sum((p["basis"] for p in parts if p["part"] in ("balance", "shares", "savings")), ZERO)
        results[member_id] = {
            "basis": basis,
            "gross": sum((p["amount"] for p in parts), ZERO),
            "detail": {
                "basis": cycle.basis,
                "parts": parts,
                "month_end_balances": main.get(member_id, {}).get("balances", {}),
                "savings_month_end_balances": savings.get(member_id, {}).get("balances", {}),
            },
        }
    return results
