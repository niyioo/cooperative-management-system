import datetime
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.configuration.models import CooperativeSettings
from apps.ledger.models import Transaction
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

CONTRIBUTIONS = "/api/v1/admin/savings/contributions/"
WITHDRAWALS = "/api/v1/admin/savings/withdrawals/"
ACCOUNTS = "/api/v1/admin/savings/accounts/"


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def saver(db, this_year):
    return MemberFactory(date_joined=datetime.date(this_year - 1, 1, 1))


@pytest.fixture
def xmas_account(open_cycle, saver):
    return SavingsAccount.objects.get_or_create(member=saver, cycle=open_cycle, defaults={"product": open_cycle.product})[0]


@pytest.fixture
def regular_account(saver, regular):
    return SavingsAccount.objects.create(member=saver, product=regular)


def contribute(client, account, amount="5000", period=None, **extra):
    payload = {"account": str(account.pk), "amount": amount, **extra}
    if period:
        payload["period"] = period
    return client.post(CONTRIBUTIONS, payload, format="json")


def require_approval_for(txn_type):
    coop = CooperativeSettings.load()
    coop.maker_checker_types = [*coop.maker_checker_types, txn_type]
    coop.save()


class TestChristmasContributions:
    def test_contribution_posts_and_updates_the_balance(self, as_user, accountant, xmas_account, this_year):
        response = contribute(as_user(accountant), xmas_account, period=f"{this_year}-03")
        assert response.status_code == 201, response.data
        assert response.data["status"] == "POSTED"
        assert response.data["type_label"] == "Christmas Savings contribution"
        assert response.data["period"] == datetime.date(this_year, 3, 1).isoformat()
        account = as_user(accountant).get(f"{ACCOUNTS}{xmas_account.pk}/").data
        assert account["balance"] == "5000.00"

    def test_november_is_outside_the_window(self, as_user, accountant, xmas_account, this_year):
        response = contribute(as_user(accountant), xmas_account, period=f"{this_year}-11")
        assert code(response) == "contribution_rejected"
        assert "outside" in response.data["error"]["message"]

    def test_month_is_required(self, as_user, accountant, xmas_account):
        assert code(contribute(as_user(accountant), xmas_account)) == "contribution_rejected"

    def test_one_contribution_per_month(self, as_user, accountant, xmas_account, this_year):
        client = as_user(accountant)
        contribute(client, xmas_account, period=f"{this_year}-03")
        again = contribute(client, xmas_account, period=f"{this_year}-03")
        assert "already been recorded" in again.data["error"]["message"]

    def test_multiple_per_month_when_the_product_allows(self, as_user, accountant, xmas_account, christmas, this_year):
        christmas.allow_multiple_contributions_per_period = True
        christmas.save()
        client = as_user(accountant)
        contribute(client, xmas_account, period=f"{this_year}-03")
        assert contribute(client, xmas_account, period=f"{this_year}-03").status_code == 201

    def test_closed_cycle_refuses_contributions(self, as_user, accountant, treasurer, xmas_account, open_cycle, this_year):
        as_user(treasurer).post(f"/api/v1/admin/savings/cycles/{open_cycle.pk}/close/")
        response = contribute(as_user(accountant), xmas_account, period=f"{this_year}-03")
        assert "not open" in response.data["error"]["message"]

    def test_frozen_account_and_inactive_member_are_refused(self, as_user, accountant, xmas_account, saver, this_year):
        xmas_account.status = SavingsAccount.Status.FROZEN
        xmas_account.save()
        assert "frozen" in contribute(as_user(accountant), xmas_account, period=f"{this_year}-03").data["error"]["message"]
        xmas_account.status = SavingsAccount.Status.ACTIVE
        xmas_account.save()
        Member.objects.filter(pk=saver.pk).update(status=Member.Status.INACTIVE)
        assert "Inactive" in contribute(as_user(accountant), xmas_account, period=f"{this_year}-03").data["error"]["message"]

    def test_minimum_contribution(self, as_user, accountant, xmas_account, christmas, this_year):
        christmas.min_contribution = Decimal("1000")
        christmas.save()
        assert "minimum" in contribute(as_user(accountant), xmas_account, "500", period=f"{this_year}-03").data["error"]["message"]

    def test_officer_cannot_post_to_own_account(self, as_user, accountant, open_cycle, this_year):
        own = MemberFactory(user=accountant, date_joined=datetime.date(this_year - 1, 1, 1))
        account = SavingsAccount.objects.create(member=own, product=open_cycle.product, cycle=open_cycle)
        assert code(contribute(as_user(accountant), account, period=f"{this_year}-03")) == "self_dealing"

    def test_future_value_date(self, as_user, accountant, xmas_account, this_year):
        response = contribute(as_user(accountant), xmas_account, period=f"{this_year}-03", value_date="2999-01-01")
        assert code(response) == "future_date"


class TestRegularContributions:
    def test_period_defaults_to_the_value_date_month(self, as_user, accountant, regular_account):
        response = contribute(as_user(accountant), regular_account, "6000", value_date="2026-02-14")
        assert response.data["period"] == "2026-02-01"


class TestMakerChecker:
    def test_configured_types_wait_for_a_second_officer(self, as_user, accountant, treasurer, xmas_account, this_year):
        require_approval_for("SAVINGS_CONTRIBUTION")
        entry = contribute(as_user(accountant), xmas_account, period=f"{this_year}-04").data
        assert entry["status"] == "PENDING"
        assert as_user(accountant).get(f"{ACCOUNTS}{xmas_account.pk}/").data["balance"] == "0.00"

        # Accountants don't hold approve_transaction; treasurers do, but not for their own entries.
        assert as_user(accountant).post(f"/api/v1/admin/transactions/{entry['id']}/approve/").status_code == 403
        approved = as_user(treasurer).post(f"/api/v1/admin/transactions/{entry['id']}/approve/")
        assert approved.data["status"] == "POSTED"
        assert approved.data["approved_by"] == treasurer.full_name
        assert AuditLog.objects.filter(action="ledger.entry_approved").exists()

    def test_creator_cannot_approve_own_entry(self, as_user, treasurer, xmas_account, this_year):
        require_approval_for("SAVINGS_CONTRIBUTION")
        entry = contribute(as_user(treasurer), xmas_account, period=f"{this_year}-04").data
        response = as_user(treasurer).post(f"/api/v1/admin/transactions/{entry['id']}/approve/")
        assert code(response) == "maker_checker"

    def test_creator_can_cancel_own_pending_entry(self, as_user, accountant, xmas_account, this_year):
        require_approval_for("SAVINGS_CONTRIBUTION")
        entry = contribute(as_user(accountant), xmas_account, period=f"{this_year}-04").data
        response = as_user(accountant).post(f"/api/v1/admin/transactions/{entry['id']}/reject/", {"reason": "Wrong month"})
        assert response.data["status"] == "REJECTED"
        assert AuditLog.objects.filter(action="ledger.entry_cancelled").exists()

    def test_pending_list(self, as_user, accountant, treasurer, xmas_account, this_year):
        require_approval_for("SAVINGS_CONTRIBUTION")
        contribute(as_user(accountant), xmas_account, period=f"{this_year}-05")
        assert as_user(treasurer).get("/api/v1/admin/transactions/pending/").data["count"] == 1


class TestWithdrawals:
    def test_emdi_products_do_not_allow_withdrawals(self, as_user, treasurer, regular_account):
        response = as_user(treasurer).post(
            WITHDRAWALS, {"account": str(regular_account.pk), "amount": "100", "reason": "Emergency"}, format="json"
        )
        assert code(response) == "withdrawal_not_allowed"

    def test_enabled_withdrawal_needs_balance_and_approval(self, as_user, accountant, treasurer, regular_account, regular):
        regular.allow_officer_withdrawal = True
        regular.save()
        contribute(as_user(accountant), regular_account, "6000")
        client = as_user(treasurer)
        too_much = client.post(WITHDRAWALS, {"account": str(regular_account.pk), "amount": "8000", "reason": "Emergency"}, format="json")
        assert code(too_much) == "insufficient_balance"

        entry = client.post(WITHDRAWALS, {"account": str(regular_account.pk), "amount": "1000", "reason": "Emergency"}, format="json").data
        assert entry["status"] == "PENDING"  # withdrawals are maker-checker by default
        chairman = make_officer("Cooperative Chairman")
        as_user(chairman).post(f"/api/v1/admin/transactions/{entry['id']}/approve/")
        assert as_user(treasurer).get(f"{ACCOUNTS}{regular_account.pk}/").data["balance"] == "5000.00"


class TestGrid:
    def test_grid_shows_each_month(self, as_user, accountant, open_cycle, this_year):
        first = MemberFactory(last_name="Adebayo", date_joined=datetime.date(this_year - 1, 1, 1))
        second = MemberFactory(last_name="Bello", date_joined=datetime.date(this_year - 1, 1, 1))
        client = as_user(accountant)
        for member, months in ((first, ["01", "02"]), (second, ["02"])):
            account = SavingsAccount.objects.get_or_create(member=member, cycle=open_cycle, defaults={"product": open_cycle.product})[0]
            for month in months:
                contribute(client, account, "5000", period=f"{this_year}-{month}")

        grid = client.get(f"/api/v1/admin/savings/cycles/{open_cycle.pk}/grid/").data["results"]
        assert grid["months"][0] == f"{this_year}-01" and grid["months"][-1] == f"{this_year}-10"
        rows = {r["member_name"].split()[-1]: r for r in grid["rows"]}
        assert rows["Adebayo"]["months"][f"{this_year}-02"] == "5000.00"
        assert rows["Adebayo"]["total"] == "10000.00"
        assert rows["Adebayo"]["expected_total"] == "50000.00"
        assert grid["totals"][f"{this_year}-02"] == "10000.00"
        assert grid["totals"]["total"] == "15000.00"


def test_members_cannot_use_savings_admin(as_user, member):
    assert as_user(member.user).get(ACCOUNTS).status_code == 403
    assert Transaction.objects.count() == 0
