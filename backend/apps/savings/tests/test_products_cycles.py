import datetime

import pytest

from apps.ledger.models import Transaction
from apps.members.models import Member
from apps.savings import services
from apps.savings.models import SavingsAccount, SavingsCycle
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/admin/savings/products/"
CYCLES = "/api/v1/admin/savings/cycles/"


def code(response):
    return response.data["error"]["code"]


class TestProducts:
    def test_create_regular_product(self, as_user, treasurer):
        response = as_user(treasurer).post(
            PRODUCTS,
            {"name": "Special Savings", "code": "special", "kind": "REGULAR", "cycle_start_month": 1, "cycle_end_month": 3},
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["code"] == "SPECIAL"
        assert response.data["cycle_start_month"] is None  # ignored for regular products

    def test_cycle_product_needs_a_window(self, as_user, treasurer):
        response = as_user(treasurer).post(PRODUCTS, {"name": "Sallah Savings", "code": "SALLAH", "kind": "CYCLE"}, format="json")
        assert code(response) == "cycle_months_required"

    def test_duplicate_code(self, as_user, treasurer):
        response = as_user(treasurer).post(PRODUCTS, {"name": "Another", "code": "christmas", "kind": "REGULAR"}, format="json")
        assert code(response) == "duplicate_code"

    def test_kind_is_locked_once_accounts_exist(self, as_user, treasurer, regular, member):
        SavingsAccount.objects.create(member=member, product=regular)
        response = as_user(treasurer).patch(
            f"{PRODUCTS}{regular.pk}/", {"kind": "CYCLE", "cycle_start_month": 1, "cycle_end_month": 10}, format="json"
        )
        assert code(response) == "kind_locked"

    def test_any_officer_lists_but_only_product_managers_create(self, as_user):
        loan_officer = make_officer("Loan Officer")
        assert as_user(loan_officer).get(PRODUCTS).status_code == 200
        assert as_user(loan_officer).post(PRODUCTS, {"name": "X", "code": "X", "kind": "REGULAR"}).status_code == 403


class TestCycles:
    def test_create_cycle_uses_the_product_window(self, as_user, treasurer, christmas):
        response = as_user(treasurer).post(CYCLES, {"product": christmas.pk, "year": 2027, "expected_monthly_contribution": "5000"}, format="json")
        assert response.status_code == 201, response.data
        assert response.data["name"] == "Christmas Savings 2027"
        assert response.data["start_date"] == "2027-01-01"
        assert response.data["end_date"] == "2027-10-31"
        assert response.data["status"] == "UPCOMING"
        again = as_user(treasurer).post(CYCLES, {"product": christmas.pk, "year": 2027}, format="json")
        assert code(again) == "duplicate_cycle"

    def test_regular_product_cannot_have_cycles(self, as_user, treasurer, regular):
        assert code(as_user(treasurer).post(CYCLES, {"product": regular.pk, "year": 2027}, format="json")) == "not_cycle_product"

    def test_opening_gives_eligible_active_members_accounts(self, as_user, treasurer, christmas, this_year):
        christmas.min_membership_months = 3
        christmas.save()
        long_standing = datetime.date(this_year - 1, 1, 1)
        active = MemberFactory(date_joined=long_standing)
        MemberFactory(date_joined=long_standing, status=Member.Status.PENDING)
        MemberFactory(date_joined=long_standing, status=Member.Status.SUSPENDED)
        MemberFactory()  # joined today: under the 3-month minimum

        cycle = services.create_cycle(treasurer, product=christmas, year=this_year)
        response = as_user(treasurer).post(f"{CYCLES}{cycle.pk}/open/")
        assert response.status_code == 200
        assert response.data["status"] == "OPEN"
        assert response.data["accounts_opened"] == 1
        assert list(SavingsAccount.objects.filter(cycle=cycle).values_list("member_id", flat=True)) == [active.pk]
        assert code(as_user(treasurer).post(f"{CYCLES}{cycle.pk}/open/")) == "invalid_cycle_status"

    def test_only_one_open_cycle_per_product(self, as_user, treasurer, open_cycle, christmas, this_year):
        next_year = services.create_cycle(treasurer, product=christmas, year=this_year + 1)
        assert code(as_user(treasurer).post(f"{CYCLES}{next_year.pk}/open/")) == "previous_cycle_open"

    def test_close_blocked_by_pending_entries(self, as_user, treasurer, accountant, open_cycle, this_year):
        from apps.configuration.models import CooperativeSettings

        coop = CooperativeSettings.load()
        coop.maker_checker_types = [*coop.maker_checker_types, "SAVINGS_CONTRIBUTION"]
        coop.save()
        member = MemberFactory()
        account = SavingsAccount.objects.create(member=member, product=open_cycle.product, cycle=open_cycle)
        services.post_contribution(accountant, account=account, amount=5000, period=datetime.date(this_year, 3, 1))

        assert code(as_user(treasurer).post(f"{CYCLES}{open_cycle.pk}/close/")) == "pending_entries"
        Transaction.objects.filter(savings_account=account).update(status="REJECTED")
        response = as_user(treasurer).post(f"{CYCLES}{open_cycle.pk}/close/")
        assert response.data["status"] == "CLOSED"

    def test_expected_amount_changes_only_before_opening(self, as_user, treasurer, open_cycle):
        response = as_user(treasurer).patch(f"{CYCLES}{open_cycle.pk}/", {"expected_monthly_contribution": "7000"}, format="json")
        assert code(response) == "cycle_started"

    def test_cycle_list_shows_totals(self, as_user, treasurer, open_cycle):
        data = as_user(treasurer).get(CYCLES).data["results"][0]
        assert data["status"] == SavingsCycle.Status.OPEN
        assert data["total_saved"] == "0.00"


class TestOpeningAccounts:
    def test_open_account_once(self, as_user, accountant, regular, member):
        # Regression: UUID primary keys are set before saving, so "does it exist yet?" must not look at pk.
        client = as_user(accountant)
        response = client.post("/api/v1/admin/savings/accounts/", {"member": str(member.pk), "product": str(regular.pk)})
        assert response.status_code == 201, response.data
        assert response.data["account_number"].startswith("SV")
        again = client.post("/api/v1/admin/savings/accounts/", {"member": str(member.pk), "product": str(regular.pk)})
        assert code(again) == "account_exists"
