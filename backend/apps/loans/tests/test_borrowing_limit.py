"""BR-32: total borrowing is limited to 3x the member's Regular Savings (the statutory monthly contributions)."""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import DomainError
from apps.configuration.models import CooperativeSettings
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.loans.eligibility import current_borrowing, eligible_savings, evaluate
from apps.savings.models import SavingsAccount, SavingsProduct
from tests.factories import MemberFactory, accept_guarantees, add_guarantors

from .helpers import give_savings

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def open_product(product):
    """The Regular Loan without a product multiple of its own, so only the cooperative's 3x applies."""
    product.max_savings_multiple = None
    product.save()
    return product


@pytest.fixture
def saver(db):
    member = MemberFactory(date_joined=datetime.date(2020, 1, 1))
    give_savings(member, "100000")
    return member


def apply(officer, member, product, amount):
    application = services.create_application(officer, member=member, product=product,
                                              amount_requested=D(amount), term_months=12, purpose="Fees")
    add_guarantors(officer, application)
    return application


def borrowing_check(result):
    return next(c for c in result["checks"] if c["code"] == "borrowing_limit")


class TestBorrowingLimit:
    def test_members_may_borrow_three_times_their_regular_savings(self, saver, open_product):
        result = evaluate(saver, open_product, amount=D("300000"), term_months=12)
        assert result["max_amount"] == D("300000.00")
        assert borrowing_check(result)["passed"]
        assert borrowing_check(result)["label"] == "Total borrowing within 3× Regular Savings"
        assert not borrowing_check(evaluate(saver, open_product, amount=D("300000.01"), term_months=12))["passed"]

    def test_only_regular_savings_count(self, saver, open_product):
        christmas = SavingsProduct.objects.get(code="CHRISTMAS")
        account = SavingsAccount.objects.create(member=saver, product=christmas)
        Transaction.objects.create(member=saver, txn_type="SAVINGS_OPENING_BALANCE", entry_side="CREDIT", amount=D("500000"),
                                   savings_account=account, status="POSTED", posted_at=timezone.now())
        assert eligible_savings(saver) == D("100000.00")
        assert evaluate(saver, open_product)["max_amount"] == D("300000.00")

    def test_what_is_already_owed_counts_against_the_limit(self, saver, open_product, loan_officer, chairman, treasurer):
        application = apply(loan_officer, saver, open_product, "120000")
        services.submit_application(loan_officer, application)
        accept_guarantees(application)
        services.start_review(loan_officer, application)
        services.approve_application(chairman, application)
        assert current_borrowing(saver) == D("120000.00")  # approved, not yet paid out

        loan = services.disburse(treasurer, application)
        ledger.approve_entry(chairman, Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT"))
        owed = current_borrowing(saver)
        assert owed >= D("120000.00")  # principal plus any interest charged

        emergency = open_product.__class__.objects.create(name="Emergency", code="EMG", interest_rate=D("5"), min_amount=D("1000"),
                                                          max_amount=D("1000000"), min_term_months=1, max_term_months=12)
        assert evaluate(saver, emergency)["max_amount"] == D("300000.00") - owed

        too_much = apply(loan_officer, saver, emergency, str(D("300000.00") - owed + 1))
        with pytest.raises(DomainError) as refused:
            services.submit_application(loan_officer, too_much)
        assert refused.value.code == "not_eligible"

    def test_a_product_can_be_stricter(self, saver, product):
        assert product.max_savings_multiple == D("2")
        assert evaluate(saver, product)["max_amount"] == D("200000.00")

    def test_blank_setting_means_no_cooperative_limit(self, saver, open_product):
        CooperativeSettings.objects.update(loan_savings_multiple=None)
        result = evaluate(saver, open_product)
        assert result["max_amount"] == open_product.max_amount
        assert all(c["code"] != "borrowing_limit" for c in result["checks"])

    def test_default_is_three(self):
        assert CooperativeSettings.load().loan_savings_multiple == D("3.00")
