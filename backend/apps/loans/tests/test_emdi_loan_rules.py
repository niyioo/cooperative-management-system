"""BR-37: EMDI's own loan rules (figures are made up)."""
import datetime
from decimal import Decimal

import pytest

from apps.common.exceptions import DomainError
from apps.configuration.models import CooperativeSettings
from apps.loans import services
from apps.loans.calculators import end_month_deadline, longest_term_before, schedule_for_product
from apps.loans.eligibility import evaluate, maximum_amount
from apps.loans.models import Loan, LoanProduct
from apps.members.models import Member
from tests.factories import MemberFactory, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db
D = Decimal


def product(code, **terms):
    defaults = dict(name=code, interest_rate=D("12"), interest_rate_basis="PER_LOAN", interest_method="FLAT",
                    interest_collection="AMORTISED", min_amount=D("1000"), max_amount=D("50000000"),
                    min_term_months=1, max_term_months=18, guarantors_required=0)
    defaults.update(terms)
    return LoanProduct.objects.create(code=code, **defaults)


@pytest.fixture
def regular(db):
    return product("COOP", name="Cooperative Loan", max_savings_multiple=D("3"), official_savings_multiple=D("4"),
                   guarantors_required=2)


@pytest.fixture
def commodity(db):
    return product("COMD", name="Commodity Loan", loan_type="COMMODITY", interest_rate=D("10"), max_amount=D("200000"),
                   max_term_months=3, must_end_by_month=10)


@pytest.fixture
def christmas(db):
    return product("XMAS", name="Christmas Loan", loan_type="CHRISTMAS", interest_rate=D("20"), max_term_months=6,
                   must_end_by_month=10, open_to_non_members=True)


def checks(result):
    return {c["code"]: c for c in result["checks"]}


def test_interest_is_charged_once_on_the_amount_borrowed(regular):
    schedule = schedule_for_product(regular, D("100000"), 12, datetime.date(2026, 1, 21))
    assert schedule.total_interest == D("12000.00")  # 12% of the loan, whatever the term
    assert schedule.monthly_payment == D("9333.33")
    assert schedule_for_product(regular, D("100000"), 18, datetime.date(2026, 1, 21)).total_interest == D("12000.00")


def test_officials_may_borrow_four_times_their_savings(regular):
    member, official = MemberFactory(), MemberFactory(is_official=True)
    give_savings(member, "100000")
    give_savings(official, "100000")
    assert maximum_amount(regular, member) == D("300000.00")
    assert maximum_amount(regular, official) == D("400000.00")
    assert not checks(evaluate(member, regular, amount=D("350000"), term_months=12))["savings_security"]["passed"]
    assert checks(evaluate(official, regular, amount=D("350000"), term_months=12))["savings_security"]["passed"]


def test_loans_must_end_by_october():
    assert end_month_deadline(datetime.date(2026, 1, 21), 10) == datetime.date(2026, 10, 31)
    assert longest_term_before(datetime.date(2026, 1, 21), 10) == 9  # February to October
    assert longest_term_before(datetime.date(2026, 9, 15), 10) == 1  # only October is left
    assert end_month_deadline(datetime.date(2026, 10, 5), 10) == datetime.date(2027, 10, 31)  # first due in November


def test_an_application_running_past_october_is_refused(monkeypatch, christmas):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda: datetime.date(2026, 8, 10))
    member = MemberFactory()
    result = evaluate(member, christmas, amount=D("200000"), term_months=6)
    assert not result["eligible"] and not checks(result)["end_month"]["passed"]  # Sept and Oct only
    assert evaluate(member, christmas, amount=D("200000"), term_months=2)["eligible"]


def test_christmas_loans_are_open_to_christmas_savers(christmas, regular):
    saver = MemberFactory(membership_type=Member.Type.CHRISTMAS_SAVER, membership_number="XMAS/9")
    assert checks(evaluate(saver, christmas, amount=D("50000"), term_months=1))["full_member"]["passed"]
    assert not checks(evaluate(saver, regular, amount=D("50000"), term_months=1))["full_member"]["passed"]


def test_one_loan_per_product_and_three_at_most(regular, commodity, christmas):
    CooperativeSettings.objects.update(max_running_loans=3)
    member = MemberFactory()
    for p in (regular, commodity, christmas):
        Loan.objects.create(member=member, product=p, principal=D("10000"), interest_rate=D("10"), term_months=3,
                            disbursed_on=datetime.date(2026, 1, 1), first_due_date=datetime.date(2026, 2, 28),
                            maturity_date=datetime.date(2026, 4, 30), status=Loan.Status.ACTIVE, is_migrated=True)
    same = checks(evaluate(member, commodity, amount=D("10000"), term_months=1))
    assert not same["active_loan_limit"]["passed"]  # repay the commodity loan before another
    electronics = product("ELEC", name="Electronics Loan", loan_type="ELECTRONICS", max_amount=D("500000"), max_term_months=6)
    fourth = checks(evaluate(member, electronics, amount=D("10000"), term_months=1))
    assert not fourth["running_loan_limit"]["passed"]


def test_officers_see_whether_pay_covers_it_but_decide(regular):
    member = MemberFactory(monthly_net_pay=D("50000"))
    give_savings(member, "1000000")
    result = evaluate(member, regular, amount=D("1200000"), term_months=12)  # ₦112,000 a month
    pay = checks(result)["pay_covers"]
    assert not pay["passed"] and not pay["hard"] and "net pay ₦50,000.00" in pay["detail"]


def test_the_secretary_collates_and_the_chairman_approves(as_user, commodity):
    secretary, chairman, treasurer = (make_officer(r) for r in ("Cooperative Secretary", "Cooperative Chairman", "Treasurer"))
    member = MemberFactory()
    application = services.create_application(secretary, member=member, product=commodity, amount_requested=D("100000"),
                                              term_months=1, purpose="Foodstuff", items_description="Rice and oil")
    services.submit_application(secretary, application)
    services.start_review(secretary, application)
    with pytest.raises(Exception):
        services.approve_application(treasurer, application)  # the treasurer pays loans out but no longer approves
    approved = services.approve_application(chairman, application)
    assert approved.status == "APPROVED"


def test_whoever_collated_cannot_also_approve(commodity):
    chairman = make_officer("Cooperative Chairman")
    application = services.create_application(chairman, member=MemberFactory(), product=commodity,
                                              amount_requested=D("50000"), term_months=1, purpose="Goods",
                                              items_description="Fridge")
    services.submit_application(chairman, application)
    services.start_review(chairman, application)
    with pytest.raises(DomainError) as error:
        services.approve_application(chairman, application)
    assert error.value.code == "maker_checker"


def test_goods_loans_need_the_goods_described(commodity):
    secretary = make_officer("Cooperative Secretary")
    application = services.create_application(secretary, member=MemberFactory(), product=commodity,
                                              amount_requested=D("50000"), term_months=1, purpose="Goods")
    with pytest.raises(DomainError) as error:
        services.submit_application(secretary, application)
    assert error.value.code == "items_required"
