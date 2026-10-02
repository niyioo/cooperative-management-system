from apps.accounts.perms import P
from apps.closures.models import AccountClosureRequest
from apps.dividends.selectors import member_dividend_history
from apps.investments.selectors import member_investment_position
from apps.ledger.choices import TransactionStatus
from apps.ledger.selectors import member_transactions
from apps.ledger.serializers import TransactionSerializer
from apps.loans.models import Loan, LoanApplication
from apps.loans.selectors import loan_schedule, member_loan_position, next_instalment
from apps.notifications.selectors import visible_announcements
from apps.savings.selectors import member_savings_position

def financial_summary(member, viewer):
    """
    The member profile's financial sections. Each section appears only if the
    viewing officer may see that module (least privilege), e.g. the Secretary
    sees the profile but not balances.
    """
    summary = {}
    if viewer.has_perm(P.VIEW_SAVINGS):
        summary["savings"] = member_savings_position(member)
    if viewer.has_perm(P.VIEW_LOANS):
        summary["loans"] = member_loan_position(member)
    if viewer.has_perm(P.VIEW_INVESTMENTS):
        summary["investments"] = member_investment_position(member)
    if viewer.has_perm(P.VIEW_DIVIDENDS):
        summary["dividends"] = member_dividend_history(member, published_only=False)
    return summary


def member_dashboard(member):
    """Everything the member portal's home page shows, in one call."""
    savings = member_savings_position(member)
    loans = member_loan_position(member)
    investments = member_investment_position(member)
    dividends = member_dividend_history(member, published_only=True)

    upcoming = None
    for loan in Loan.objects.filter(member=member, status__in=Loan.RUNNING_STATUSES).prefetch_related("installments"):
        nxt = next_instalment(loan_schedule(loan))
        if nxt and (upcoming is None or nxt["due_date"] < upcoming["due_date"]):
            upcoming = {**nxt, "loan_id": str(loan.pk), "loan_reference": loan.reference}

    recent = member_transactions(member).exclude(status=TransactionStatus.REJECTED)[:5]
    applications = LoanApplication.objects.filter(member=member, status__in=LoanApplication.OPEN_STATUSES).select_related("product")
    closure = AccountClosureRequest.objects.filter(member=member, status__in=AccountClosureRequest.OPEN_STATUSES).first()

    return {
        "member": {
            "id": str(member.pk),
            "full_name": member.full_name,
            "first_name": member.first_name,
            "membership_number": member.membership_number,
            "status": member.status,
            "status_label": member.get_status_display(),
            "date_joined": member.date_joined,
        },
        "summary": {
            "christmas_savings": savings["christmas"]["balance"],
            "christmas_year": savings["christmas"]["year"],
            "other_savings": savings["other"]["balance"],
            "total_savings": savings["total"],
            "active_loans": loans["active_count"],
            "active_loan_principal": loans["active_principal"],
            "outstanding_loan": loans["outstanding"],
            "investment": investments["total_principal"],
            "latest_dividend": dividends["latest"],
        },
        "upcoming_repayment": upcoming,
        "loan_applications": [
            {
                "id": str(a.pk),
                "reference": a.reference,
                "product": a.product.name,
                "amount_requested": a.amount_requested,
                "status": a.status,
                "status_label": a.get_status_display(),
            }
            for a in applications
        ],
        "recent_transactions": TransactionSerializer(recent, many=True).data,
        "announcements": [
            {"id": str(a.pk), "title": a.title, "body": a.body, "is_important": a.is_important, "publish_at": a.publish_at}
            for a in visible_announcements()[:5]
        ],
        "unread_notifications": member.user.notifications.filter(read_at__isnull=True).count(),
        "closure_request": (
            {"id": str(closure.pk), "reference": closure.reference, "status": closure.status, "status_label": closure.get_status_display()}
            if closure else None
        ),
    }
