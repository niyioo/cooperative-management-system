import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.closures import services as closures
from apps.closures.models import AccountClosureRequest
from apps.configuration.models import CooperativeSettings
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.ledger import services as ledger
from apps.ledger.models import Transaction, TransactionBatch
from apps.loans import services as loans
from apps.loans.models import Loan, LoanProduct
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, accept_guarantees, add_guarantors, make_officer

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/closure-requests/"
D = Decimal


def code(response):
    return response.data["error"]["code"]


def credit(member, field, account, amount, txn_type):
    return Transaction.objects.create(member=member, txn_type=txn_type, entry_side="CREDIT", amount=D(amount),
                                      status="POSTED", posted_at=timezone.now(), **{field: account})


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


@pytest.fixture
def leaver(regular, this_year):
    """A retiring member with ₦100,000 savings and ₦40,000 investments."""
    member = MemberFactory(date_joined=datetime.date(this_year - 5, 1, 1))
    credit(member, "savings_account", SavingsAccount.objects.create(member=member, product=regular), "100000", "SAVINGS_OPENING_BALANCE")
    shares = InvestmentProduct.objects.create(name="Share Capital", code="SHARES")
    credit(member, "investment_account", InvestmentAccount.objects.create(member=member, product=shares), "40000", "INVESTMENT_CONTRIBUTION")
    return member


@pytest.fixture
def approved_request(leaver, secretary, chairman):
    request = closures.submit_request(leaver, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
    closures.start_review(secretary, request)
    return closures.approve_request(chairman, request)


def give_loan(member, amount="120000"):
    coop = CooperativeSettings.load()
    coop.maker_checker_types = []
    coop.save()
    product = LoanProduct.objects.create(name="Regular Loan", code="REG", interest_rate=D("10"), min_amount=D("1000"),
                                         max_amount=D("1000000"), min_term_months=1, max_term_months=24)
    officer, chairman, treasurer = make_officer("Loan Officer"), make_officer("Cooperative Chairman"), make_officer("Treasurer")
    application = loans.create_application(officer, member=member, product=product, amount_requested=D(amount), term_months=12, purpose="x")
    add_guarantors(officer, application)
    loans.submit_application(officer, application)
    accept_guarantees(application)
    loans.start_review(officer, application)
    loans.approve_application(chairman, application)
    loan = loans.disburse(treasurer, application)
    coop.maker_checker_types = coop._meta.get_field("maker_checker_types").default()
    coop.save()
    return loan


class TestWorkflow:
    def test_review_then_approve_freezes_the_settlement(self, as_user, leaver, secretary, chairman):
        request = closures.submit_request(leaver, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
        assert code(as_user(chairman).post(f"{URL}{request.pk}/approve/")) == "invalid_transition"  # review first
        assert as_user(secretary).post(f"{URL}{request.pk}/start-review/").data["status"] == "UNDER_REVIEW"
        approved = as_user(chairman).post(f"{URL}{request.pk}/approve/", {"notes": "Settle in November"}).data
        assert approved["status"] == "APPROVED"
        statement = approved["settlement_statement"]
        assert statement["savings_total"] == "100000.00" and statement["investment_total"] == "40000.00"
        assert statement["net_payable"] == "140000.00"
        leaver.refresh_from_db()
        assert leaver.status == Member.Status.ACTIVE  # approval alone closes nothing

    def test_reject_needs_a_reason(self, as_user, leaver, chairman):
        request = closures.submit_request(leaver, reason_category="OTHER", reason="x", confirmed=True)
        assert code(as_user(chairman).post(f"{URL}{request.pk}/reject/", {})) == "validation_error"
        assert as_user(chairman).post(f"{URL}{request.pk}/reject/", {"reason": "Loan guarantor obligations"}).data["status"] == "REJECTED"

    def test_secretary_reviews_but_cannot_execute(self, as_user, approved_request, secretary):
        assert as_user(secretary).post(f"{URL}{approved_request.pk}/execute/").status_code == 403


class TestExecution:
    def test_settlement_pays_out_then_closes_after_second_approval(self, as_user, leaver, approved_request, treasurer, chairman):
        response = as_user(treasurer).post(f"{URL}{approved_request.pk}/execute/")
        assert response.status_code == 200, response.data
        batch = response.data["batch"]
        assert batch["batch_type"] == "CLOSURE_SETTLEMENT" and batch["total_amount"] == "140000.00"
        assert response.data["request"]["status"] == "APPROVED"  # not closed until the batch posts
        assert code(as_user(treasurer).post(f"{URL}{approved_request.pk}/execute/")) == "settlement_in_progress"

        as_user(treasurer).post(f"/api/v1/admin/batches/{batch['id']}/submit/")
        assert as_user(chairman).post(f"/api/v1/admin/batches/{batch['id']}/approve/").data["status"] == "POSTED"

        approved_request.refresh_from_db()
        leaver.refresh_from_db()
        leaver.user.refresh_from_db()
        assert approved_request.status == AccountClosureRequest.Status.CLOSED
        assert leaver.status == Member.Status.CLOSED and leaver.closed_at
        assert leaver.user.is_active is False  # portal login disabled by default
        for account in SavingsAccount.objects.filter(member=leaver):
            assert account.status == "CLOSED" and ledger.posted_balance(account) == 0
        assert InvestmentAccount.objects.get(member=leaver).status == "LIQUIDATED"  # paid out in full by the settlement
        assert Transaction.objects.filter(member=leaver).count() > 0  # history kept (BR-13)

    def test_loans_are_offset_from_savings_first(self, as_user, leaver, secretary, chairman, treasurer):
        loan = give_loan(leaver, "100000")  # owes ₦110,000 with flat interest
        request = closures.submit_request(leaver, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
        closures.start_review(secretary, request)
        closures.approve_request(chairman, request)
        _, batch = closures.execute(treasurer, request)
        lines = list(Transaction.objects.filter(batch=batch).order_by("created_at").values_list("txn_type", "amount"))
        assert lines == [
            ("SAVINGS_WITHDRAWAL", D("100000.00")),
            ("INVESTMENT_LIQUIDATION", D("10000.00")),
            ("LOAN_REPAYMENT", D("110000.00")),
            ("INVESTMENT_LIQUIDATION", D("30000.00")),
        ]
        ledger.submit_batch(treasurer, batch)
        ledger.approve_batch(chairman, batch)
        loan.refresh_from_db()
        assert loan.status == Loan.Status.COMPLETED

    def test_execution_blocked_when_loans_exceed_savings(self, leaver, secretary, chairman, treasurer):
        give_loan(leaver, "500000")
        request = closures.submit_request(leaver, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
        closures.start_review(secretary, request)
        closures.approve_request(chairman, request)
        with pytest.raises(closures.DomainError) as exc:
            closures.execute(treasurer, request)
        assert exc.value.code == "loans_not_covered"
        assert not TransactionBatch.objects.filter(batch_type="CLOSURE_SETTLEMENT").exists()

    def test_member_with_nothing_to_settle_is_closed_at_once(self, as_user, secretary, chairman, treasurer):
        member = MemberFactory()
        request = closures.submit_request(member, reason_category="TRANSFER", reason="Transferred", confirmed=True)
        closures.start_review(secretary, request)
        closures.approve_request(chairman, request)
        response = as_user(treasurer).post(f"{URL}{request.pk}/execute/")
        assert response.data["batch"] is None and response.data["request"]["status"] == "CLOSED"

    def test_officer_cannot_close_own_account(self, secretary, chairman):
        own = MemberFactory(user=make_officer("Treasurer"))
        request = closures.submit_request(own, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
        closures.start_review(secretary, request)
        closures.approve_request(chairman, request)
        with pytest.raises(closures.DomainError) as exc:
            closures.execute(own.user, request)
        assert exc.value.code == "self_dealing"


def test_dashboard_sections_follow_permissions(as_user, leaver, secretary, treasurer):
    full = as_user(treasurer).get("/api/v1/admin/dashboard/").data
    assert {"members", "savings", "loans", "investments", "dividends", "transactions", "approvals", "trends"} <= set(full)
    assert full["savings"]["other"] == "100000.00" and full["investments"]["total"] == "40000.00"
    assert len(full["trends"]) == 12 and "savings_contributions" in full["trends"][0]

    limited = as_user(secretary).get("/api/v1/admin/dashboard/").data
    assert "members" in limited and "savings" not in limited and "loans" not in limited
    assert "closure_requests" in limited["approvals"]
