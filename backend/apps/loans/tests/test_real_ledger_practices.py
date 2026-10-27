"""Practices from EMDI's own ledgers: loans brought forward at go-live, the Christmas bonus,
officer withdrawals that keep loans secured, commodity loans and existing member numbers."""
import datetime
from decimal import Decimal

import pytest

from apps.common.exceptions import DomainError
from apps.configuration.models import CooperativeSettings
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.loans.models import Loan, LoanProduct
from apps.members.models import Member
from apps.members.tests.helpers import xlsx_file
from apps.notifications.models import Notification
from apps.savings import services as savings
from apps.savings.models import SavingsAccount, SavingsCycle
from tests.factories import MemberFactory, accept_guarantees, add_guarantors, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db
D = Decimal
BATCHES = "/api/v1/admin/batches/"
BALANCE_DATE = datetime.date(2025, 12, 31)


@pytest.fixture
def reducing(db):
    """EMDI's loans: 1% a month on the reducing balance, repaid in equal monthly instalments."""
    return LoanProduct.objects.create(
        name="Regular Loan (1%)", code="REG1", interest_rate=D("1"), interest_rate_basis="PER_MONTH",
        interest_method="REDUCING_BALANCE", interest_collection="AMORTISED", min_amount=D("1000"),
        max_amount=D("10000000"), min_term_months=1, max_term_months=120,
    )


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


class TestLoansBroughtForward:
    def test_the_monthly_repayment_sets_the_term(self, reducing):
        months = services.term_for_repayment(reducing, D("850000"), D("80000"), BALANCE_DATE)
        first = services.schedule_for_product(reducing, D("850000"), months, BALANCE_DATE).instalments[0]
        assert first.principal + first.interest <= D("80000")
        assert first.interest == D("8500.00")  # 1% of the balance, as in the ledger
        assert services.term_for_repayment(reducing, D("850000"), D("8000"), BALANCE_DATE) is None  # never repays

    def test_a_batch_brings_running_loans_forward(self, as_user, reducing, chairman):
        officer = make_officer("Treasurer")
        member = MemberFactory(membership_number="501")
        header = ["Membership number", "Product code", "Outstanding", "Monthly repayment", "Balance date", "Reference"]
        upload = xlsx_file(header, [["501", "REG1", 850000, 80000, "2025-12-31", "Ledger p.7"]])
        batch = as_user(officer).post(BATCHES, {"batch_type": "LOAN_OPENING_BALANCES", "file": upload}, format="multipart").data
        assert batch["status"] == "VALIDATED", batch["validation_report"]

        loan = Loan.objects.get(member=member)
        assert loan.is_migrated and loan.application is None and loan.status == Loan.Status.PENDING_DISBURSEMENT
        as_user(officer).post(f"{BATCHES}{batch['id']}/submit/")
        assert as_user(chairman).post(f"{BATCHES}{batch['id']}/approve/").data["status"] == "POSTED"

        loan.refresh_from_db()
        assert loan.status == Loan.Status.ACTIVE and loan.principal == D("850000.00")
        entry = Transaction.objects.get(loan=loan, txn_type="LOAN_OPENING_BALANCE")
        assert entry.value_date == BALANCE_DATE and entry.external_reference == "Ledger p.7"
        assert not Notification.objects.filter(recipient=member.user, title__contains="disbursed").exists()

    def test_rows_are_checked_and_a_rejected_batch_cancels_the_loans(self, as_user, reducing, chairman):
        officer = make_officer("Treasurer")
        MemberFactory(membership_number="502")
        saver = MemberFactory(membership_number="XMAS/1", membership_type=Member.Type.CHRISTMAS_SAVER)
        header = ["Membership number", "Product code", "Outstanding", "Monthly repayment", "Months left", "Balance date"]
        rows = [["502", "REG1", 600000, "", 7, "2025-12-31"], [saver.membership_number, "REG1", 1000, 100, "", "2025-12-31"],
                ["502", "NOPE", 1000, 100, "", "2025-12-31"], ["502", "REG1", 1000, "", "", "2025-12-31"]]
        bad = as_user(officer).post(BATCHES, {"batch_type": "LOAN_OPENING_BALANCES", "file": xlsx_file(header, rows)},
                                    format="multipart").data
        errors = {e["row"]: e["errors"] for e in bad["validation_report"]["errors"]}
        assert set(errors) == {3, 4, 5}
        assert "cannot hold a loan" in errors[3]["membership_number"][0]

        good = as_user(officer).post(BATCHES, {"batch_type": "LOAN_OPENING_BALANCES", "file": xlsx_file(header, rows[:1])},
                                     format="multipart").data
        loan = Loan.objects.get(member__membership_number="502", status=Loan.Status.PENDING_DISBURSEMENT)
        assert loan.term_months == 7
        as_user(officer).post(f"{BATCHES}{good['id']}/submit/")
        as_user(chairman).post(f"{BATCHES}{good['id']}/reject/", {"reason": "Wrong figures"}, format="json")
        loan.refresh_from_db()
        assert loan.status == Loan.Status.CANCELLED


class TestChristmasBonus:
    def test_the_bonus_is_paid_with_the_savings(self, as_user, accountant, treasurer, open_cycle, this_year):
        saver = MemberFactory(date_joined=datetime.date(this_year - 1, 1, 1))
        account = SavingsAccount.objects.get_or_create(member=saver, cycle=open_cycle, defaults={"product": open_cycle.product})[0]
        savings.post_contribution(accountant, account=account, amount=D("100000"), period=datetime.date(this_year, 3, 1))
        cycles = "/api/v1/admin/savings/cycles/"
        secretary = make_officer("Cooperative Secretary")
        assert as_user(secretary).post(f"{cycles}{open_cycle.pk}/bonus/", {"bonus_rate": "8.90"}, format="json").status_code == 403
        admin = make_officer("Super Administrator")
        assert as_user(admin).post(f"{cycles}{open_cycle.pk}/bonus/", {"bonus_rate": "8.90"}, format="json").data["bonus_rate"] == "8.90"

        as_user(treasurer).post(f"{cycles}{open_cycle.pk}/close/")
        batch = as_user(treasurer).post(f"{cycles}{open_cycle.pk}/payout/").data
        lines = Transaction.objects.filter(batch_id=batch["id"])
        assert lines.get(txn_type="SAVINGS_CYCLE_BONUS").amount == D("8900.00")
        assert lines.get(txn_type="SAVINGS_CYCLE_PAYOUT").amount == D("108900.00")
        assert as_user(admin).post(f"{cycles}{open_cycle.pk}/bonus/", {"bonus_rate": "9"}, format="json").data["error"]["code"] == "payout_in_progress"

        as_user(treasurer).post(f"{BATCHES}{batch['id']}/submit/")
        chairman = make_officer("Cooperative Chairman")
        assert as_user(chairman).post(f"{BATCHES}{batch['id']}/approve/").data["status"] == "POSTED"
        assert ledger.posted_balance(account) == 0
        assert "including a bonus of ₦8,900.00" in Notification.objects.get(recipient=saver.user, title__contains="paid out").body
        grid = as_user(treasurer).get(f"{cycles}{open_cycle.pk}/grid/").data["results"]
        assert grid["totals"]["total"] == "100000.00" and grid["totals"]["bonus"] == "8900.00"
        assert grid["totals"]["paid_out"] == "108900.00"
        assert SavingsCycle.objects.get(pk=open_cycle.pk).status == SavingsCycle.Status.PAID_OUT


class TestOfficerWithdrawals:
    def test_a_withdrawal_cannot_leave_loans_under_secured(self, approved, borrower, treasurer, chairman):
        # Borrower has 100,000 in Regular Savings; 180,000 + 21,600 interest owed needs at least 67,200 at 3x.
        loan = services.disburse(treasurer, approved("180000"))
        ledger.approve_entry(chairman, Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT"))
        account = SavingsAccount.objects.get(member=borrower, product__code="REGULAR")
        with pytest.raises(DomainError) as refused:
            savings.post_withdrawal(treasurer, account=account, amount=D("50000"), reason="School fees")
        assert refused.value.code == "loans_unsecured"
        assert "At most ₦32,800.00" in str(refused.value)
        entry = savings.post_withdrawal(treasurer, account=account, amount=D("5000"), reason="School fees")
        assert entry.status == "PENDING"  # a second officer approves it

    def test_a_withdrawal_cannot_leave_guarantees_under_secured(self, product, loan_officer, treasurer):
        guarantor = MemberFactory(date_joined=datetime.date(2020, 1, 1))
        account = give_savings(guarantor, "50000")
        borrower = MemberFactory(date_joined=datetime.date(2020, 1, 1))
        give_savings(borrower, "100000")
        application = services.create_application(loan_officer, member=borrower, product=product, amount_requested=D("90000"),
                                                  term_months=6, purpose="x")
        services.add_guarantor(loan_officer, application, guarantor.membership_number)
        services.submit_application(loan_officer, application)
        accept_guarantees(application)
        CooperativeSettings.objects.update(guarantor_savings_multiple=D("2"))
        with pytest.raises(DomainError) as refused:
            savings.post_withdrawal(treasurer, account=account, amount=D("10000"), reason="x")
        assert refused.value.code == "guarantees_unsecured"


class TestCommodityLoans:
    @pytest.fixture
    def commodity(self, db):
        return LoanProduct.objects.create(name="Commodity Loan", code="COM", loan_type="COMMODITY", interest_rate=D("1"),
                                          interest_rate_basis="PER_MONTH", interest_method="REDUCING_BALANCE",
                                          min_amount=D("1000"), max_amount=D("1000000"), min_term_months=1, max_term_months=12)

    def test_goods_and_supplier_are_required(self, borrower, commodity, loan_officer, chairman, treasurer):
        application = services.create_application(loan_officer, member=borrower, product=commodity, amount_requested=D("60000"),
                                                  term_months=6, purpose="Household")
        add_guarantors(loan_officer, application)
        with pytest.raises(DomainError) as refused:
            services.submit_application(loan_officer, application)
        assert refused.value.code == "items_required"

        services.update_application(loan_officer, application, items_description="Deep freezer (Haier Thermocool 300L)")
        services.submit_application(loan_officer, application)
        accept_guarantees(application)
        services.start_review(loan_officer, application)
        services.approve_application(chairman, application)
        with pytest.raises(DomainError) as refused:
            services.disburse(treasurer, application)
        assert refused.value.code == "supplier_required"
        loan = services.disburse(treasurer, application, supplier="Akure Home Appliances")
        assert loan.supplier == "Akure Home Appliances"
        assert Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT").description.startswith("Goods from Akure Home Appliances")


class TestExistingMemberNumbers:
    def test_new_numbers_skip_ones_already_taken(self):
        CooperativeSettings.objects.update(membership_number_format="{seq}")
        MemberFactory(membership_number="1")
        MemberFactory(membership_number="2")
        assert Member.generate_membership_number() == "3"

    def test_the_society_has_its_registered_name(self):
        assert CooperativeSettings.load().name == "EMDI Cooperative Multipurpose Society Ltd"


def test_savings_opening_balances_can_be_dated(as_user, regular):
    officer, approver = make_officer("Accountant"), make_officer("Treasurer")
    member = MemberFactory(membership_number="503")
    header = ["Membership number", "Product code", "Amount", "Balance date"]
    batch = as_user(officer).post(BATCHES, {"batch_type": "OPENING_BALANCES", "file": xlsx_file(header, [["503", "REGULAR", 900000, "31/12/2025"]])},
                                  format="multipart").data
    assert batch["status"] == "VALIDATED", batch["validation_report"]
    as_user(officer).post(f"{BATCHES}{batch['id']}/submit/")
    as_user(approver).post(f"{BATCHES}{batch['id']}/approve/")
    entry = Transaction.objects.get(member=member, txn_type="SAVINGS_OPENING_BALANCE")
    assert entry.value_date == BALANCE_DATE and entry.amount == D("900000.00")
