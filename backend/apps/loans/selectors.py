from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from apps.configuration.models import CooperativeSettings
from apps.ledger.choices import TransactionStatus
from apps.ledger.selectors import ZERO, net_by

from .models import Loan, LoanApplication, RepaymentAllocation


def member_loan_position(member):
    """Outstanding = debits (disbursement, interest, penalties) - credits (repayments)."""
    nets = net_by("loan", member=member)
    loans = Loan.objects.filter(member=member).exclude(status=Loan.Status.CANCELLED).select_related("product")
    entries = [
        {
            "id": str(loan.pk),
            "reference": loan.reference,
            "product": loan.product.name,
            "principal": loan.principal,
            "total_interest": loan.total_interest,
            "outstanding": -nets.get(loan.pk, ZERO),
            "status": loan.status,
            "disbursed_on": loan.disbursed_on,
            "maturity_date": loan.maturity_date,
        }
        for loan in loans.order_by("-disbursed_on")
    ]
    active = [e for e in entries if e["status"] in Loan.RUNNING_STATUSES]
    open_applications = LoanApplication.objects.filter(
        member=member, status__in=LoanApplication.OPEN_STATUSES
    ).count()
    return {
        "active_count": len(active),
        "active_principal": sum((e["principal"] for e in active), ZERO),
        "outstanding": sum((e["outstanding"] for e in active), ZERO),
        "open_applications": open_applications,
        "loans": entries,
    }


def _paid_map(loan_ids):
    rows = (
        RepaymentAllocation.objects.filter(
            installment__loan_id__in=loan_ids, repayment__transaction__status=TransactionStatus.POSTED
        )
        .values("installment")
        .annotate(principal=Sum("principal_amount"), interest=Sum("interest_amount"))
    )
    return {r["installment"]: (r["principal"], r["interest"]) for r in rows}


def _instalment_rows(loan, paid, today, grace):
    rows = []
    for inst in loan.installments.all():
        principal_paid, interest_paid = paid.get(inst.pk, (ZERO, ZERO))
        due = inst.principal_due + inst.interest_due
        settled = principal_paid + interest_paid
        remaining = due - settled
        if remaining <= 0:
            status = "PAID"
        elif inst.due_date + timedelta(days=grace) < today:
            status = "OVERDUE"
        elif inst.due_date <= today:
            status = "DUE"
        else:
            status = "PARTIAL" if settled > 0 else "UPCOMING"
        rows.append(
            {
                "number": inst.number,
                "due_date": inst.due_date,
                "principal_due": inst.principal_due,
                "interest_due": inst.interest_due,
                "total_due": due,
                "paid": settled,
                "remaining": remaining,
                "status": status,
            }
        )
    return rows


def loan_schedule(loan, today=None):
    today = today or timezone.localdate()
    grace = CooperativeSettings.load().loan_overdue_grace_days
    return _instalment_rows(loan, _paid_map([loan.pk]), today, grace)


def arrears_from_rows(rows, today):
    overdue = [r for r in rows if r["status"] == "OVERDUE"]
    oldest = overdue[0]["due_date"] if overdue else None
    return {
        "amount": sum((r["remaining"] for r in overdue), ZERO),
        "instalments": len(overdue),
        "oldest_due_date": oldest,
        "days_overdue": (today - oldest).days if oldest else 0,
    }


def loan_arrears(loan, today=None):
    today = today or timezone.localdate()
    return arrears_from_rows(loan_schedule(loan, today), today)


def next_instalment(rows):
    return next((r for r in rows if r["remaining"] > 0), None)


def overdue_loans(today=None):
    """Running loans with at least one overdue instalment, worst first."""
    today = today or timezone.localdate()
    grace = CooperativeSettings.load().loan_overdue_grace_days
    loans = list(
        Loan.objects.filter(status__in=Loan.RUNNING_STATUSES, first_due_date__lt=today - timedelta(days=grace))
        .select_related("member", "product")
        .prefetch_related("installments")
    )
    paid = _paid_map([l.pk for l in loans])
    outstanding = {}
    for loan_id, net in net_by("loan", loan__in=loans).items():
        outstanding[loan_id] = -net
    result = []
    for loan in loans:
        arrears = arrears_from_rows(_instalment_rows(loan, paid, today, grace), today)
        if arrears["amount"] > 0:
            result.append({"loan": loan, "arrears": arrears, "outstanding": outstanding.get(loan.pk, ZERO)})
    result.sort(key=lambda r: (-r["arrears"]["days_overdue"], -r["arrears"]["amount"]))
    return result
