"""BR-35: a dividend paid in parts, the way EMDI's schedule works (figures here are made up)."""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.dividends import services
from apps.dividends.models import MemberDividend
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.ledger.models import Transaction
from apps.loans.models import Loan, LoanProduct, LoanRepayment
from apps.savings.models import SavingsAccount, SavingsProduct
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db
D = Decimal
CYCLES = "/api/v1/admin/dividends/cycles/"


def posted(member, txn_type, side, amount, on, **account):
    return Transaction.objects.create(member=member, txn_type=txn_type, entry_side=side, amount=D(amount), value_date=on,
                                      status="POSTED", posted_at=timezone.now(), **account)


def interest_paid(member, amount, on):
    product, _ = LoanProduct.objects.get_or_create(code="PART", defaults=dict(
        name="Loan", interest_rate=D("1"), min_amount=D("1"), max_amount=D("9999999"), min_term_months=1, max_term_months=60))
    loan = Loan.objects.create(member=member, product=product, principal=D("500000"), interest_rate=D("1"), term_months=12,
                               disbursed_on=on, first_due_date=on, maturity_date=on, status=Loan.Status.ACTIVE, is_migrated=True)
    entry = posted(member, "LOAN_REPAYMENT", "CREDIT", amount, on, loan=loan)
    LoanRepayment.objects.create(transaction=entry, loan=loan, interest_component=D(amount))


@pytest.fixture
def year(this_year):
    return this_year - 1


@pytest.fixture
def books(year):
    """Ade: ₦20,000 shares, ₦700,000 savings, ₦50,000 loan interest paid. Bisi: ₦23,000 shares, ₦1,000,000 savings, no loan."""
    shares = InvestmentProduct.objects.create(name="Share Capital", code="SHARES")
    regular = SavingsProduct.objects.get(code="REGULAR")
    ade, bisi = MemberFactory(last_name="Ade"), MemberFactory(last_name="Bisi")
    on = datetime.date(year, 3, 1)
    for member, share, saved in ((ade, "20000", "700000"), (bisi, "23000", "1000000")):
        posted(member, "INVESTMENT_OPENING_BALANCE", "CREDIT", share, on,
               investment_account=InvestmentAccount.objects.create(member=member, product=shares))
        account, _ = SavingsAccount.objects.get_or_create(member=member, product=regular, cycle=None)
        posted(member, "SAVINGS_OPENING_BALANCE", "CREDIT", saved, on, savings_account=account)
    interest_paid(ade, "50000", datetime.date(year, 6, 30))
    interest_paid(ade, "9999", datetime.date(year - 1, 6, 30))  # last year's interest does not count
    return {"shares": shares, "regular": regular}


def emdi_cycle(actor, year, books, **overrides):
    terms = dict(
        financial_year=year, basis="CLOSING_BALANCE", cutoff_date=datetime.date(year, 12, 31),
        eligible_investment_products=[books["shares"]], eligible_savings_products=[books["regular"]],
        rate=D("10.35"), savings_rate=D("1.2"), interest_refund_rate=D("32.5"), round_down_to_naira=True,
        allowances=[{"name": "Food", "amount": "1000"}, {"name": "Gift", "amount": "1000"}],
    )
    terms.update(overrides)
    return services.create_cycle(actor, **terms)


def by_name(run):
    return {d.member.last_name: d for d in MemberDividend.objects.filter(run=run).select_related("member")}


def test_each_part_is_worked_out_and_added_up(accountant, year, books):
    run, _ = services.calculate(accountant, emdi_cycle(accountant, year, books))
    ade, bisi = by_name(run)["Ade"], by_name(run)["Bisi"]
    # Ade: 10.35% of 20,000 + 1.2% of 700,000 + 32.5% of 50,000 + Food + Gift
    assert ade.gross_amount == D("2070") + D("8400") + D("16250") + D("2000")
    # Bisi: 10.35% of 23,000 is 2,380.50, kept as 2,380; no loan, so no interest refund
    assert bisi.gross_amount == D("2380") + D("12000") + D("2000")
    parts = {p.get("name", p["part"]): D(p["amount"]) for p in ade.calculation_detail["parts"]}
    assert parts == {"shares": D("2070.00"), "savings": D("8400.00"), "interest_refund": D("16250.00"),
                     "Food": D("1000.00"), "Gift": D("1000.00")}
    assert ade.basis_amount == D("720000.00") and run.total_gross == ade.gross_amount + bisi.gross_amount


def test_an_amount_to_share_sets_the_interest_refund_rate(accountant, year, books):
    cycle = emdi_cycle(accountant, year, books, interest_refund_rate=0, interest_refund_pool=D("10000"))
    run, _ = services.calculate(accountant, cycle)
    refund = next(p for p in by_name(run)["Ade"].calculation_detail["parts"] if p["part"] == "interest_refund")
    assert D(refund["amount"]) == D("10000.00") and D(refund["rate"]) == D("20.0000")


def test_rate_and_amount_cannot_both_be_given(as_user, accountant, year, books):
    response = as_user(accountant).post(CYCLES, {
        "financial_year": year, "rate": "10", "interest_refund_rate": "30", "interest_refund_pool": "5000"}, format="json")
    assert response.data["error"]["code"] == "refund_rate_and_pool"


def test_the_api_takes_and_returns_the_parts(as_user, accountant, year, books):
    response = as_user(accountant).post(CYCLES, {
        "financial_year": year, "rate": "10.35", "savings_rate": "1.2", "interest_refund_rate": "32.5", "basis": "CLOSING_BALANCE",
        "cutoff_date": f"{year}-12-31", "round_down_to_naira": True,
        "eligible_investment_products": [str(books["shares"].pk)], "eligible_savings_products": [str(books["regular"].pk)],
        "allowances": [{"name": "Food", "amount": "1000"}],
    }, format="json")
    assert response.status_code == 201, response.data
    assert response.data["allowances"] == [{"name": "Food", "amount": "1000.00"}]
    assert response.data["savings_rate"] == "1.2000" and response.data["round_down_to_naira"] is True
    bad = as_user(accountant).patch(f"{CYCLES}{response.data['id']}/", {"allowances": [{"name": "", "amount": "5"}]}, format="json")
    assert bad.status_code == 400


def test_publishing_a_cycle_with_parts_tells_members_their_total(accountant, year, books):
    from apps.notifications.models import Notification

    cycle = emdi_cycle(accountant, year, books)
    services.calculate(accountant, cycle)
    chairman = make_officer("Cooperative Chairman")
    services.approve(chairman, cycle)
    services.publish(chairman, cycle)
    note = Notification.objects.filter(title=f"Your {year} dividend").order_by("body").first()
    assert "declared." in note.body and "%" not in note.body
