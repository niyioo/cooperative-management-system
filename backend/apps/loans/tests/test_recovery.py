"""BR-36: what a borrower owes can be taken from their own savings, approved by a second officer."""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.loans.models import LoanProduct
from apps.notifications.models import Notification
from tests.factories import MemberFactory, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db
D = Decimal
LOANS = "/api/v1/admin/loans/"
BATCHES = "/api/v1/admin/batches/"


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


@pytest.fixture
def behind(super_admin, chairman):
    """A borrower with ₦300,000 in Regular Savings and a ₦200,000 loan that has gone unpaid for months."""
    product = LoanProduct.objects.create(
        name="Regular Loan", code="REGR", interest_rate=D("1"), interest_rate_basis="PER_MONTH",
        interest_method="REDUCING_BALANCE", interest_collection="AMORTISED", min_amount=D("1000"),
        max_amount=D("10000000"), min_term_months=1, max_term_months=60,
    )
    member = MemberFactory()
    savings = give_savings(member, "300000")
    started = timezone.localdate().replace(day=1) - datetime.timedelta(days=200)
    loan = services.bring_forward_loan(super_admin, member=member, product=product, outstanding=D("200000"),
                                       monthly_repayment=D("20000"), balance_date=started)
    entry = Transaction.objects.get(loan=loan)
    if entry.status == "PENDING":
        ledger.approve_entry(chairman, entry)
    loan.refresh_from_db()
    return {"member": member, "loan": loan, "savings": savings}


def test_the_form_shows_what_is_owed_and_what_savings_hold(as_user, treasurer, behind):
    data = as_user(treasurer).get(f"{LOANS}{behind['loan'].pk}/recover/").data
    assert D(data["arrears"]) > 0 and data["days_overdue"] > 0
    assert D(data["outstanding"]) == services.repayable(behind["loan"])
    assert [(a["id"], D(a["available"])) for a in data["accounts"]] == [(str(behind["savings"].pk), D("300000.00"))]


def test_recovery_moves_money_from_savings_into_the_loan_once_approved(as_user, treasurer, chairman, behind):
    loan, savings = behind["loan"], behind["savings"]
    owed_before = services.repayable(loan)
    response = as_user(treasurer).post(f"{LOANS}{loan.pk}/recover/", {
        "savings_account": str(savings.pk), "amount": "50000", "reason": "Six months of missed deductions",
    })
    assert response.status_code == 201, response.data
    batch = response.data
    assert batch["batch_type"] == "LOAN_RECOVERY" and batch["line_count"] == 2
    assert ledger.posted_balance(savings) == D("300000")  # nothing moves until approval

    # Only one recovery at a time, and the preparer cannot approve it.
    again = as_user(treasurer).post(f"{LOANS}{loan.pk}/recover/", {
        "savings_account": str(savings.pk), "amount": "1000", "reason": "again"})
    assert again.data["error"]["code"] == "recovery_in_progress"
    as_user(treasurer).post(f"{BATCHES}{batch['id']}/submit/")
    assert as_user(treasurer).post(f"{BATCHES}{batch['id']}/approve/").data["error"]["code"] == "maker_checker"

    assert as_user(chairman).post(f"{BATCHES}{batch['id']}/approve/").data["status"] == "POSTED"
    assert ledger.posted_balance(savings) == D("250000.00")
    assert services.repayable(loan) == owed_before - D("50000")
    note = Notification.objects.get(recipient=behind["member"].user, title="Loan repayment taken from your savings")
    assert "Six months of missed deductions" in note.body


def test_recovery_cannot_take_more_than_is_owed_or_held(as_user, treasurer, behind):
    url = f"{LOANS}{behind['loan'].pk}/recover/"
    account = str(behind["savings"].pk)
    too_much = as_user(treasurer).post(url, {"savings_account": account, "amount": "9000000", "reason": "x"})
    assert too_much.data["error"]["code"] == "overpayment"

    other = give_savings(MemberFactory(), "1000")  # someone else's account
    wrong = as_user(treasurer).post(url, {"savings_account": str(other.pk), "amount": "100", "reason": "x"})
    assert wrong.data["error"]["code"] == "wrong_member"

    no_reason = as_user(treasurer).post(url, {"savings_account": account, "amount": "100", "reason": " "})
    assert no_reason.status_code == 400


def test_savings_must_hold_the_amount(as_user, treasurer, super_admin, chairman):
    product = LoanProduct.objects.create(
        name="Big Loan", code="BIGR", interest_rate=D("1"), interest_rate_basis="PER_MONTH",
        interest_method="REDUCING_BALANCE", interest_collection="AMORTISED", min_amount=D("1000"),
        max_amount=D("10000000"), min_term_months=1, max_term_months=60,
    )
    member = MemberFactory()
    savings = give_savings(member, "40000")
    loan = services.bring_forward_loan(super_admin, member=member, product=product, outstanding=D("500000"),
                                       term_months=24, balance_date=timezone.localdate() - datetime.timedelta(days=90))
    entry = Transaction.objects.get(loan=loan)
    if entry.status == "PENDING":
        ledger.approve_entry(chairman, entry)
    response = as_user(treasurer).post(f"{LOANS}{loan.pk}/recover/", {
        "savings_account": str(savings.pk), "amount": "45000", "reason": "Arrears"})
    assert response.data["error"]["code"] == "insufficient_balance"


def test_a_member_without_the_permissions_cannot_recover(as_user, secretary, behind):
    response = as_user(secretary).post(f"{LOANS}{behind['loan'].pk}/recover/", {
        "savings_account": str(behind["savings"].pk), "amount": "100", "reason": "x"})
    assert response.status_code == 403
