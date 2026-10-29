"""Closed loopholes around guarantors, closure and payroll repayments (BR-28, BR-30)."""
import datetime
from decimal import Decimal

import pytest

from apps.closures import services as closures
from apps.common.exceptions import DomainError
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.members.models import Member
from apps.members.tests.helpers import xlsx_file
from tests.factories import MemberFactory, accept_guarantees, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db
D = Decimal
BATCHES = "/api/v1/admin/batches/"


def ask_to_close(member):
    return closures.submit_request(member, reason_category="RETIREMENT", reason="Retiring", confirmed=True)


def running_loan(approved, treasurer, chairman):
    application = approved()
    loan = services.disburse(treasurer, application, disbursed_on=datetime.date.today() - datetime.timedelta(days=40))
    ledger.approve_entry(chairman, Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT"))
    loan.refresh_from_db()
    return loan


class TestGuarantorCannotLeaveFirst:
    def test_closure_is_refused_while_their_guaranteed_loan_runs(self, approved, treasurer, chairman, super_admin):
        loan = running_loan(approved, treasurer, chairman)
        guarantor = loan.application.guarantors.get().guarantor
        request = ask_to_close(guarantor)
        closures.start_review(super_admin, request)

        statement = closures.settlement_statement(guarantor)
        assert statement["can_settle"] is False
        assert statement["guarantees"][0]["loan_application"] == loan.application.reference

        with pytest.raises(DomainError) as refused:
            closures.approve_request(super_admin, request)
        assert refused.value.code == "guarantor_of_running_loan"
        assert loan.application.reference in str(refused.value)

    def test_members_leaving_cannot_be_chosen_or_accept(self, borrower, product, loan_officer):
        leaving = MemberFactory()
        ask_to_close(leaving)
        application = services.create_application(loan_officer, member=borrower, product=product,
                                                  amount_requested=D("50000"), term_months=6, purpose="Fees")
        with pytest.raises(DomainError) as refused:
            services.add_guarantor(loan_officer, application, leaving.membership_number)
        assert refused.value.code == "guarantor_not_active"

        friend = MemberFactory()
        guarantee = services.add_guarantor(loan_officer, application, friend.membership_number)
        services.submit_application(loan_officer, application)
        ask_to_close(friend)
        guarantee.refresh_from_db()
        with pytest.raises(DomainError) as refused:
            services.respond_to_guarantee(friend.user, guarantee, accept=True)
        assert refused.value.code == "guarantor_not_active"


class TestApprovalRechecksGuarantors:
    def test_a_guarantor_suspended_after_accepting_no_longer_counts(self, borrower, product, loan_officer, chairman):
        application = services.create_application(loan_officer, member=borrower, product=product,
                                                  amount_requested=D("50000"), term_months=6, purpose="Fees")
        friend = MemberFactory()
        services.add_guarantor(loan_officer, application, friend.membership_number)
        services.submit_application(loan_officer, application)
        accept_guarantees(application)
        services.start_review(loan_officer, application)
        Member.objects.filter(pk=friend.pk).update(status=Member.Status.SUSPENDED)

        with pytest.raises(DomainError) as refused:
            services.approve_application(chairman, application)
        assert refused.value.code == "guarantors_required"
        assert friend.full_name in str(refused.value)


class TestPayrollRepaymentsOncePerMonth:
    @pytest.fixture
    def accountant(self, db):
        return make_officer("Accountant")

    def upload(self, client, rows):
        return client.post(BATCHES, {"batch_type": "LOAN_REPAYMENTS", "file": xlsx_file(["Membership number", "Amount", "Month"], rows)},
                           format="multipart").data

    def test_a_repeated_row_in_one_file_is_refused(self, as_user, accountant, approved, treasurer, chairman, borrower):
        running_loan(approved, treasurer, chairman)
        rows = [[borrower.membership_number, 1000, "2026-02"], [borrower.membership_number, 1000, "2026-02"]]
        batch = self.upload(as_user(accountant), rows)
        assert batch["status"] == "DRAFT"
        assert "already on row" in batch["validation_report"]["errors"][0]["errors"]["period"][0]

    def test_the_same_month_cannot_be_uploaded_twice(self, as_user, accountant, approved, treasurer, chairman, borrower):
        running_loan(approved, treasurer, chairman)
        client = as_user(accountant)
        first = self.upload(client, [[borrower.membership_number, 1000, "2026-02"]])
        assert first["status"] == "VALIDATED", first["validation_report"]

        # Still awaiting approval: the month is already claimed.
        again = self.upload(client, [[borrower.membership_number, 1000, "2026-02"]])
        assert again["status"] == "DRAFT"
        assert "already been recorded" in again["validation_report"]["errors"][0]["errors"]["period"][0]

        client.post(f"{BATCHES}{first['id']}/submit/")
        assert as_user(treasurer).post(f"{BATCHES}{first['id']}/approve/").data["status"] == "POSTED"
        assert self.upload(client, [[borrower.membership_number, 1000, "2026-02"]])["status"] == "DRAFT"
        assert self.upload(client, [[borrower.membership_number, 1000, "2026-03"]])["status"] == "VALIDATED"

    def test_cash_repayments_in_the_same_month_are_still_allowed(self, as_user, accountant, approved, treasurer, chairman, borrower):
        loan = running_loan(approved, treasurer, chairman)
        services.record_repayment(accountant, loan, amount=D("1000"), period=datetime.date(2026, 2, 1))
        assert self.upload(as_user(accountant), [[borrower.membership_number, 1000, "2026-02"]])["status"] == "VALIDATED"


@pytest.mark.guarantee_limit
class TestGuaranteeLimit:
    """BR-31: a member may guarantee at most 2x their savings in total (a cooperative setting)."""

    @pytest.fixture
    def application(self, product, loan_officer):
        """A draft from a fresh, eligible borrower (one open application per product each)."""
        def make(amount):
            borrower = MemberFactory(date_joined=datetime.date(2020, 1, 1))
            give_savings(borrower, "100000")
            return services.create_application(loan_officer, member=borrower, product=product,
                                               amount_requested=D(amount), term_months=6, purpose="Fees")
        return make

    def test_a_member_without_savings_cannot_be_chosen(self, application, loan_officer):
        with pytest.raises(DomainError) as refused:
            services.add_guarantor(loan_officer, application("50000"), MemberFactory().membership_number)
        assert refused.value.code == "guarantee_limit"
        assert "savings" not in str(refused.value)  # the applicant is not told the guarantor's savings

    def test_a_share_above_twice_their_savings_is_refused_at_submission(self, application, loan_officer):
        friend = MemberFactory()
        give_savings(friend, "20000")  # may guarantee up to 40,000
        app = application("50000")
        services.add_guarantor(loan_officer, app, friend.membership_number)
        with pytest.raises(DomainError) as refused:
            services.submit_application(loan_officer, app)
        assert refused.value.code == "guarantee_limit"

        second = MemberFactory()
        give_savings(second, "20000")
        services.add_guarantor(loan_officer, app, second.membership_number)
        services.submit_application(loan_officer, app)  # 25,000 each fits
        assert sorted(g.amount_guaranteed for g in app.guarantors.all()) == [D("25000.00"), D("25000.00")]

    def test_earlier_guarantees_use_up_the_room(self, application, loan_officer):
        friend = MemberFactory()
        give_savings(friend, "30000")  # may guarantee up to 60,000
        first = application("40000")
        services.add_guarantor(loan_officer, first, friend.membership_number)
        services.submit_application(loan_officer, first)
        accept_guarantees(first)

        second = application("30000")
        services.add_guarantor(loan_officer, second, friend.membership_number)  # 20,000 room left
        with pytest.raises(DomainError) as refused:
            services.submit_application(loan_officer, second)
        assert refused.value.code == "guarantee_limit"

    def test_accepting_rechecks_the_limit_and_tells_the_guarantor_their_room(self, application, loan_officer):
        friend = MemberFactory()
        give_savings(friend, "30000")
        first, second = application("40000"), application("20000")
        for app in (first, second):
            services.add_guarantor(loan_officer, app, friend.membership_number)
            services.submit_application(loan_officer, app)  # both fit while neither is accepted
        accept_guarantees(first)  # 40,000 of 60,000 used
        services.respond_to_guarantee(friend.user, second.guarantors.get(), accept=True)  # exactly 60,000: fine

        third = application("10000")
        other = MemberFactory()
        give_savings(other, "100000")
        services.add_guarantor(loan_officer, third, other.membership_number)
        CooperativeSettings_multiple(None)  # chosen and submitted while the limit was off
        guarantee = services.add_guarantor(loan_officer, third, friend.membership_number)
        services.submit_application(loan_officer, third)
        CooperativeSettings_multiple(D("2"))
        guarantee.refresh_from_db()
        with pytest.raises(DomainError) as refused:
            services.respond_to_guarantee(friend.user, guarantee, accept=True)
        assert refused.value.code == "guarantee_limit"
        assert "₦0.00 more" in str(refused.value)

    def test_blank_multiple_means_no_limit(self, application, loan_officer):
        CooperativeSettings_multiple(None)
        app = application("50000")
        services.add_guarantor(loan_officer, app, MemberFactory().membership_number)
        services.submit_application(loan_officer, app)


def CooperativeSettings_multiple(value):  # noqa: N802 - reads like the setting it changes
    from apps.configuration.models import CooperativeSettings

    CooperativeSettings.objects.update(guarantor_savings_multiple=value)
