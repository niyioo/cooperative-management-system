from apps.ledger.selectors import ZERO

from .models import DividendCalculationRun, DividendCycle, MemberDividend


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
        }
        for d in qs.order_by("-cycle__financial_year")
    ]
    return {
        "total_paid": sum((h["net_amount"] for h in history if h["status"] == MemberDividend.Status.PAID), ZERO),
        "latest": history[0] if history else None,
        "history": history,
    }
