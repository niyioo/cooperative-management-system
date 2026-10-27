from apps.ledger.selectors import ZERO

from .models import DividendCalculationRun, DividendCycle, MemberDividend


PART_LABELS = {"balance": "On your balances", "shares": "On share capital", "savings": "On savings",
               "interest_refund": "Refund of loan interest paid"}


def _part_label(part):
    """One line of a dividend paid in parts (BR-35), worded for the member."""
    return {"label": part.get("name") or PART_LABELS.get(part["part"], part["part"]), "basis": part.get("basis"),
            "rate": part.get("rate"), "amount": part["amount"]}


def member_dividend_history(member, *, published_only):
    """
    Dividends from approved calculation runs. Members only ever see published
    cycles (published_only=True); officers also see approved-but-unpublished ones.
    """
    qs = MemberDividend.objects.filter(
        member=member, run__status=DividendCalculationRun.Status.APPROVED
    ).select_related("cycle")
    if published_only:
        qs = qs.filter(cycle__status__in=[DividendCycle.Status.PUBLISHED, DividendCycle.Status.PAID])
    history = [
        {
            "financial_year": d.cycle.financial_year,
            "cycle_reference": d.cycle.reference,
            "basis_amount": d.basis_amount,
            "rate": d.rate,
            "gross_amount": d.gross_amount,
            "net_amount": d.net_amount,
            "status": d.status,
            "paid_at": d.paid_at,
            "parts": [_part_label(p) for p in d.calculation_detail.get("parts", [])],
        }
        for d in qs.order_by("-cycle__financial_year")
    ]
    return {
        "total_paid": sum((h["net_amount"] for h in history if h["status"] == MemberDividend.Status.PAID), ZERO),
        "latest": history[0] if history else None,
        "history": history,
    }
