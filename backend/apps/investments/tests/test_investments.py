import datetime
from decimal import Decimal

import pytest

from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.members.models import Member
from apps.members.tests.helpers import xlsx_file
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/admin/investments/products/"
ACCOUNTS = "/api/v1/admin/investments/accounts/"


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def investment_officer(db):
    return make_officer("Investment Officer")


@pytest.fixture
def shares(db):
    return InvestmentProduct.objects.create(name="Share Capital", code="SHARES", min_amount=Decimal("1000"))


@pytest.fixture
def account(shares, member):
    return InvestmentAccount.objects.create(member=member, product=shares)


class TestProductsAndAccounts:
    def test_create_product(self, as_user, investment_officer):
        response = as_user(investment_officer).post(PRODUCTS, {"name": "Real Estate Fund", "code": "reit", "lock_in_months": 12})
        assert response.status_code == 201
        assert response.data["code"] == "REIT"
        assert code(as_user(investment_officer).post(PRODUCTS, {"name": "Other", "code": "REIT"})) == "duplicate_code"

    def test_open_account(self, as_user, investment_officer, shares, member):
        client = as_user(investment_officer)
        response = client.post(ACCOUNTS, {"member": str(member.pk), "product": str(shares.pk)})
        assert response.status_code == 201
        assert response.data["account_number"].startswith("IV")
        assert response.data["principal"] == "0.00"
        assert code(client.post(ACCOUNTS, {"member": str(member.pk), "product": str(shares.pk)})) == "account_exists"

    def test_inactive_members_cannot_invest(self, as_user, investment_officer, shares):
        inactive = MemberFactory(status=Member.Status.INACTIVE)
        assert code(as_user(investment_officer).post(ACCOUNTS, {"member": str(inactive.pk), "product": str(shares.pk)})) == "not_eligible"


class TestContributionsAndLiquidation:
    def test_contribution_raises_principal(self, as_user, investment_officer, account):
        client = as_user(investment_officer)
        assert "minimum" in client.post(f"{ACCOUNTS}{account.pk}/contributions/", {"amount": "500"}).data["error"]["message"]
        response = client.post(f"{ACCOUNTS}{account.pk}/contributions/", {"amount": "25000"})
        assert response.status_code == 201 and response.data["status"] == "POSTED"
        assert client.get(f"{ACCOUNTS}{account.pk}/").data["principal"] == "25000.00"

    def test_liquidation_is_off_unless_the_product_allows_it(self, as_user, investment_officer, account):
        response = as_user(investment_officer).post(f"{ACCOUNTS}{account.pk}/liquidations/", {"amount": "100", "reason": "Exit"})
        assert code(response) == "liquidation_not_allowed"

    def test_lock_in_then_approved_liquidation(self, as_user, investment_officer, treasurer, account, shares):
        shares.allow_officer_liquidation = True
        shares.lock_in_months = 12
        shares.save()
        client = as_user(investment_officer)
        client.post(f"{ACCOUNTS}{account.pk}/contributions/", {"amount": "30000"})
        assert code(client.post(f"{ACCOUNTS}{account.pk}/liquidations/", {"amount": "30000", "reason": "Exit"})) == "locked_in"

        InvestmentAccount.objects.filter(pk=account.pk).update(opened_on=datetime.date(2020, 1, 1))
        entry = client.post(f"{ACCOUNTS}{account.pk}/liquidations/", {"amount": "30000", "reason": "Exit"}).data
        assert entry["status"] == "PENDING"  # outflows need a second officer by default
        ledger.approve_entry(treasurer, Transaction.objects.get(pk=entry["id"]))
        account.refresh_from_db()
        assert ledger.posted_balance(account) == 0
        assert account.status == InvestmentAccount.Status.LIQUIDATED


class TestBatchesAndReturns:
    def test_payroll_contributions_open_accounts_automatically(self, as_user, accountant, shares):
        members = [MemberFactory(), MemberFactory()]
        rows = [[m.membership_number, "SHARES", 20000] for m in members]
        client = as_user(accountant)  # batch preparation needs manage_batches
        batch = client.post(
            "/api/v1/admin/batches/",
            {"batch_type": "INVESTMENTS", "file": xlsx_file(["Membership number", "Product code", "Amount"], rows)},
            format="multipart",
        ).data
        assert batch["status"] == "VALIDATED", batch["validation_report"]
        client.post(f"/api/v1/admin/batches/{batch['id']}/submit/")
        chairman = make_officer("Cooperative Chairman")
        assert as_user(chairman).post(f"/api/v1/admin/batches/{batch['id']}/approve/").data["status"] == "POSTED"
        for member in members:
            assert ledger.posted_balance(InvestmentAccount.objects.get(member=member, product=shares)) == 20000

    def test_one_opening_balance_per_account(self, as_user, accountant, shares, member):
        header = ["Membership number", "Product code", "Amount"]
        rows = [[member.membership_number, "SHARES", 250000], [member.membership_number, "SHARES", 1000]]
        batch = as_user(accountant).post(
            "/api/v1/admin/batches/", {"batch_type": "INVESTMENT_OPENING_BALANCES", "file": xlsx_file(header, rows)}, format="multipart"
        ).data
        assert "Duplicate of row 2" in batch["validation_report"]["errors"][0]["errors"]["amount"][0]

    def test_record_scheme_returns(self, as_user, investment_officer, shares):
        client = as_user(investment_officer)
        response = client.post("/api/v1/admin/investments/returns/", {"product": str(shares.pk), "financial_year": 2025, "amount_earned": "1500000"})
        assert response.status_code == 201
        assert client.get("/api/v1/admin/investments/returns/", {"financial_year": 2025}).data["count"] == 1
