"""
The officer dashboard. Each section appears only if the officer may see that
module, so a Secretary's dashboard shows members and closures but no balances.
"""
from datetime import date

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.perms import P
from apps.closures.models import AccountClosureRequest
from apps.dividends.models import DividendCalculationRun, DividendCycle, MemberDividend
from apps.ledger.choices import BatchStatus, TransactionStatus, TransactionType
from apps.ledger.models import Transaction, TransactionBatch
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO
from apps.ledger.serializers import TransactionSerializer
from apps.loans.models import Loan, LoanApplication
from apps.loans.selectors import overdue_loans
from apps.members.models import Member, MemberStatus
from apps.notifications.selectors import visible_announcements
from apps.savings.models import ProductKind

T = TransactionType
TREND_SERIES = {
    "savings_contributions": ([T.SAVINGS_CONTRIBUTION], P.VIEW_SAVINGS),
    "loan_disbursements": ([T.LOAN_DISBURSEMENT], P.VIEW_LOANS),
    "loan_repayments": ([T.LOAN_REPAYMENT], P.VIEW_LOANS),
    "investment_contributions": ([T.INVESTMENT_CONTRIBUTION], P.VIEW_INVESTMENTS),
}


def _posted():
    return Transaction.objects.posted()


def _net(queryset):
    return queryset.aggregate(total=Sum(SIGNED_AMOUNT))["total"] or ZERO


def _months(count=12):
    today = timezone.localdate()
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def officer_dashboard(user):
    can = user.has_perm
    data = {
        "generated_at": timezone.now(),
        "announcements": [
            {"id": str(a.pk), "title": a.title, "body": a.body, "is_important": a.is_important, "publish_at": a.publish_at}
            for a in visible_announcements(for_officers=True)[:5]
        ],
    }
    today = timezone.localdate()

    if can(P.VIEW_MEMBER):
        counts = Member.objects.aggregate(total=Count("id"), active=Count("id", filter=Q(status=MemberStatus.ACTIVE)))
        data["members"] = counts

    if can(P.VIEW_SAVINGS):
        savings = _posted().filter(savings_account__isnull=False)
        data["savings"] = {
            "total": _net(savings),
            "christmas": _net(savings.filter(savings_account__product__kind=ProductKind.CYCLE, savings_account__cycle__year=today.year)),
            "other": _net(savings.filter(savings_account__product__kind=ProductKind.REGULAR)),
            "christmas_year": today.year,
        }

    if can(P.VIEW_LOANS):
        running = Loan.objects.filter(status__in=Loan.RUNNING_STATUSES)
        overdue = overdue_loans()
        data["loans"] = {
            "running_count": running.count(),
            "running_principal": running.aggregate(total=Sum("principal"))["total"] or ZERO,
            "outstanding": -_net(_posted().filter(loan__status__in=Loan.RUNNING_STATUSES)),
            "overdue_count": len(overdue),
            "overdue_amount": sum((o["arrears"]["amount"] for o in overdue), ZERO),
            "overdue_members": [
                {"loan_id": str(o["loan"].pk), "reference": o["loan"].reference, "member": o["loan"].member.full_name,
                 "membership_number": o["loan"].member.membership_number, "arrears": o["arrears"]["amount"],
                 "days_overdue": o["arrears"]["days_overdue"]}
                for o in overdue[:5]
            ],
            "recent_applications": [
                {"id": str(a.pk), "reference": a.reference, "member": a.member.full_name, "product": a.product.name,
                 "amount_requested": a.amount_requested, "status": a.status, "status_label": a.get_status_display(),
                 "submitted_at": a.submitted_at}
                for a in LoanApplication.objects.exclude(status=LoanApplication.Status.DRAFT)
                .select_related("member", "product").order_by("-submitted_at")[:5]
            ],
        }

    if can(P.VIEW_INVESTMENTS):
        data["investments"] = {"total": _net(_posted().filter(investment_account__isnull=False))}

    if can(P.VIEW_DIVIDENDS):
        liability = MemberDividend.objects.filter(
            status=MemberDividend.Status.APPROVED, run__status=DividendCalculationRun.Status.APPROVED
        ).aggregate(total=Sum("net_amount"))["total"] or ZERO
        latest = DividendCycle.objects.exclude(status=DividendCycle.Status.CANCELLED).order_by("-financial_year").first()
        data["dividends"] = {
            "liability": liability,
            "latest_cycle": (
                {"id": str(latest.pk), "financial_year": latest.financial_year, "rate": latest.rate,
                 "status": latest.status, "status_label": latest.get_status_display()}
                if latest else None
            ),
        }

    if can(P.VIEW_ALL_TRANSACTIONS):
        data["transactions"] = {
            "posted_count": _posted().count(),
            "recent": TransactionSerializer(
                Transaction.objects.exclude(status=TransactionStatus.REJECTED)
                .select_related("savings_account__product", "savings_account__cycle", "loan", "investment_account__product", "member")
                .order_by("-created_at")[:8],
                many=True,
            ).data,
        }

    approvals = {}
    if can(P.APPROVE_TRANSACTION):
        approvals["entries"] = Transaction.objects.pending().filter(batch__isnull=True).count()
    if can(P.APPROVE_BATCH):
        approvals["batches"] = TransactionBatch.objects.filter(status=BatchStatus.SUBMITTED).count()
    if can(P.REVIEW_LOAN_APPLICATION):
        approvals["applications_to_review"] = LoanApplication.objects.filter(status=LoanApplication.Status.SUBMITTED).count()
    if can(P.APPROVE_LOAN_APPLICATION):
        approvals["applications_to_decide"] = LoanApplication.objects.filter(status=LoanApplication.Status.UNDER_REVIEW).count()
    if can(P.DISBURSE_LOAN):
        approvals["loans_to_disburse"] = LoanApplication.objects.filter(status=LoanApplication.Status.APPROVED).count()
    if can(P.VIEW_CLOSURE_REQUESTS):
        approvals["closure_requests"] = AccountClosureRequest.objects.filter(status__in=AccountClosureRequest.OPEN_STATUSES).count()
    data["approvals"] = approvals

    series = {name: types for name, (types, perm) in TREND_SERIES.items() if can(perm)}
    if series:
        months = _months()
        rows = (
            _posted()
            .filter(value_date__gte=months[0], txn_type__in=[t for types in series.values() for t in types])
            .annotate(month=TruncMonth("value_date"))
            .values("month", "txn_type")
            .annotate(total=Sum("amount"))
        )
        totals = {(r["month"], r["txn_type"]): r["total"] for r in rows}
        data["trends"] = [
            {"month": m.strftime("%Y-%m"), **{name: sum((totals.get((m, t), ZERO) for t in types), ZERO) for name, types in series.items()}}
            for m in months
        ]
    return data
