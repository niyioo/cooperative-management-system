import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from apps.accounts.models import User
from apps.dividends import services
from apps.dividends.calculation import measurement_points
from apps.dividends.models import DividendCalculationRun, DividendCycle, MemberDividend
from apps.dividends.selectors import member_dividend_history
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

CYCLES = "/api/v1/admin/dividends/cycles/"
D = Decimal


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def year(this_year):
    return this_year - 1


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


@pytest.fixture
def shares(db):
    return InvestmentProduct.objects.create(name="Share Capital", code="SHARES")


def invest(member, product, amount, on):
    account, _ = InvestmentAccount.objects.get_or_create(member=member, product=product, status="ACTIVE")
    return Transaction.objects.create(
        member=member, txn_type="INVESTMENT_CONTRIBUTION", entry_side="CREDIT", amount=D(amount),
        investment_account=account, value_date=on, status="POSTED", posted_at=timezone.now(),
    )


@pytest.fixture
def holders(shares, year):
    """
    Ada: ₦100,000 from January, +₦20,000 in mid-July.
    Bayo: ₦60,000 from October.
    Chidi: closed membership (excluded). Dayo: only a pending contribution (excluded).
    """
    ada, bayo, chidi, dayo = (MemberFactory(last_name=n) for n in ("Ada", "Bayo", "Chidi", "Dayo"))
    invest(ada, shares, "100000", datetime.date(year, 1, 1))
    invest(ada, shares, "20000", datetime.date(year, 7, 15))
    invest(bayo, shares, "60000", datetime.date(year, 10, 10))
    invest(chidi, shares, "50000", datetime.date(year, 1, 1))
    Member.objects.filter(pk=chidi.pk).update(status=Member.Status.CLOSED, closed_at=timezone.now())
    account = InvestmentAccount.objects.create(member=dayo, product=shares)
    Transaction.objects.create(member=dayo, txn_type="INVESTMENT_CONTRIBUTION", entry_side="CREDIT", amount=D("90000"),
                               investment_account=account, value_date=datetime.date(year, 3, 1))
    return {"ada": ada, "bayo": bayo}


def new_cycle(actor, year, **kwargs):
    return services.create_cycle(actor, financial_year=year, rate=D("10"), **kwargs)


def dividends_by_name(run):
    return {d.member.last_name: d for d in MemberDividend.objects.filter(run=run).select_related("member")}


def test_measurement_points():
    points = measurement_points(2025, datetime.date(2025, 11, 15))
    assert points[0] == datetime.date(2025, 1, 31)
    assert points[-2] == datetime.date(2025, 10, 31)
    assert points[-1] == datetime.date(2025, 11, 15)
    assert len(measurement_points(2025, datetime.date(2025, 12, 31))) == 12


class TestCalculation:
    def test_average_monthly_balance(self, accountant, holders, year):
        cycle = new_cycle(accountant, year, withholding_rate=D("10"))
        run, _ = services.calculate(accountant, cycle)
        rows = dividends_by_name(run)
        assert set(rows) == {"Ada", "Bayo"}  # closed and pending-only members excluded
        # Ada: 6 month-ends at 100k + 5 at 120k, over 11 points (Jan–Nov).
        assert rows["Ada"].basis_amount == D("109090.91")
        assert rows["Ada"].gross_amount == D("10909.09")
        assert rows["Ada"].withholding_amount == D("1090.91")
        assert rows["Ada"].net_amount == D("9818.18")
        assert rows["Bayo"].basis_amount == D("10909.09")
        assert rows["Ada"].calculation_detail["month_end_balances"][f"{year}-07"] == "120000.00"
        assert run.member_count == 2 and run.total_gross == D("12000.00")

    def test_closing_and_minimum_balance(self, accountant, holders, year):
        closing_cycle = new_cycle(accountant, year, basis="CLOSING_BALANCE")
        closing = dividends_by_name(services.calculate(accountant, closing_cycle)[0])
        assert closing["Ada"].basis_amount == D("120000.00") and closing["Bayo"].basis_amount == D("60000.00")

        services.cancel_cycle(accountant, closing_cycle, reason="Comparing bases")
        minimum = dividends_by_name(services.calculate(accountant, new_cycle(accountant, year, basis="MINIMUM_BALANCE"))[0])
        assert set(minimum) == {"Ada"}  # Bayo held nothing for most of the year
        assert minimum["Ada"].basis_amount == D("100000.00")

    def test_recalculating_keeps_the_earlier_run(self, as_user, accountant, holders, year):
        cycle = new_cycle(accountant, year)
        first, _ = services.calculate(accountant, cycle)
        as_user(accountant).patch(f"{CYCLES}{cycle.pk}/", {"rate": "12"}, format="json")
        cycle.refresh_from_db()
        assert cycle.status == DividendCycle.Status.DRAFT  # parameters changed, so it must be recalculated
        second, _ = services.calculate(accountant, cycle)

        first.refresh_from_db()
        assert first.status == DividendCalculationRun.Status.SUPERSEDED
        assert dividends_by_name(first)["Ada"].gross_amount == D("10909.09")  # untouched
        assert dividends_by_name(second)["Ada"].gross_amount == D("13090.91")
        runs = as_user(accountant).get(f"{CYCLES}{cycle.pk}/runs/").data
        assert [r["run_number"] for r in runs] == [2, 1]

    def test_surplus_ceiling(self, accountant, holders, year):
        cycle = new_cycle(accountant, year, distributable_surplus=D("5000"))
        with pytest.raises(services.DomainError) as exc:
            services.calculate(accountant, cycle)
        assert exc.value.code == "exceeds_surplus"
        assert not DividendCalculationRun.objects.filter(cycle=cycle).exists()


class TestApprovalPublicationPayment:
    def test_full_cycle(self, as_user, accountant, treasurer, chairman, holders, year):
        cycle = new_cycle(accountant, year)
        client = as_user(accountant)
        calc = client.post(f"{CYCLES}{cycle.pk}/calculate/").data
        assert calc["status"] == "CALCULATED" and calc["latest_run"]["member_count"] == 2

        assert code(as_user(accountant).post(f"{CYCLES}{cycle.pk}/approve/")) == "permission_denied"
        treasurer_calc = as_user(treasurer).post(f"{CYCLES}{cycle.pk}/calculate/").data  # run 2, by the treasurer
        assert treasurer_calc["latest_run"]["run_number"] == 2

        approved = as_user(chairman).post(f"{CYCLES}{cycle.pk}/approve/").data
        assert approved["status"] == "APPROVED"
        assert code(as_user(accountant).patch(f"{CYCLES}{cycle.pk}/", {"rate": "20"}, format="json")) == "invalid_cycle_status"

        ada = holders["ada"]
        assert member_dividend_history(ada, published_only=True)["history"] == []  # not yet visible to members
        as_user(chairman).post(f"{CYCLES}{cycle.pk}/publish/")
        assert member_dividend_history(ada, published_only=True)["latest"]["net_amount"] == D("10909.09")

        batch = as_user(treasurer).post(f"{CYCLES}{cycle.pk}/pay/").data
        assert batch["batch_type"] == "DIVIDEND_PAYMENTS" and batch["line_count"] == 2
        assert code(as_user(treasurer).post(f"{CYCLES}{cycle.pk}/pay/")) == "payment_in_progress"
        as_user(treasurer).post(f"/api/v1/admin/batches/{batch['id']}/submit/")
        assert as_user(chairman).post(f"/api/v1/admin/batches/{batch['id']}/approve/").data["status"] == "POSTED"

        cycle.refresh_from_db()
        assert cycle.status == DividendCycle.Status.PAID
        paid = dividends_by_name(cycle.approved_run)
        assert all(d.status == MemberDividend.Status.PAID and d.payment_transaction_id for d in paid.values())
        regular = SavingsAccount.objects.get(member=ada, product__code="REGULAR")
        assert ledger.posted_balance(regular) == D("10909.09")  # credited to Regular Savings
        members = as_user(chairman).get(f"{CYCLES}{cycle.pk}/member-dividends/").data["results"]
        assert {m["status"] for m in members} == {"PAID"}

    def test_calculator_cannot_approve(self, treasurer, holders, year):
        cycle = new_cycle(treasurer, year)
        services.calculate(treasurer, cycle)
        treasurer.groups.add(Group.objects.get(name="Cooperative Chairman"))
        treasurer = User.objects.get(pk=treasurer.pk)  # fresh instance: permissions are cached per object
        with pytest.raises(services.DomainError) as exc:
            services.approve(treasurer, cycle)
        assert exc.value.code == "maker_checker"

    def test_external_payment_moves_no_member_account(self, accountant, treasurer, chairman, holders, year):
        cycle = new_cycle(accountant, year, payment_method="EXTERNAL")
        services.calculate(accountant, cycle)
        services.approve(chairman, cycle)
        services.publish(chairman, cycle)
        batch = services.prepare_payment(treasurer, cycle)
        entries = Transaction.objects.filter(batch=batch)
        assert entries.count() == 2
        assert all(e.savings_account_id is None and e.investment_account_id is None for e in entries)


class TestCycleRules:
    def test_one_cycle_per_year_and_defaults(self, as_user, accountant, shares, year):
        response = as_user(accountant).post(CYCLES, {"financial_year": year, "rate": "8.5"}, format="json")
        assert response.status_code == 201, response.data
        assert response.data["cutoff_date"] == f"{year}-11-30"
        assert response.data["basis"] == "AVERAGE_MONTHLY_BALANCE"
        assert response.data["eligible_investment_products"] == [shares.pk]
        assert code(as_user(accountant).post(CYCLES, {"financial_year": year, "rate": "9"}, format="json")) == "duplicate_cycle"

    def test_cutoff_must_be_in_the_year(self, as_user, accountant, shares, year):
        response = as_user(accountant).post(CYCLES, {"financial_year": year, "rate": "8", "cutoff_date": f"{year + 1}-01-15"}, format="json")
        assert code(response) == "invalid_cutoff"

    def test_cancel_before_approval(self, as_user, accountant, holders, year):
        cycle = new_cycle(accountant, year)
        services.calculate(accountant, cycle)
        assert as_user(accountant).post(f"{CYCLES}{cycle.pk}/cancel/", {"reason": "Rate not agreed"}).data["status"] == "CANCELLED"
        assert new_cycle(accountant, year).status == DividendCycle.Status.DRAFT  # the year is free again
