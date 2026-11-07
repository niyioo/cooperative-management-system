import datetime
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.savings import services as savings
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

TXNS = "/api/v1/admin/transactions/"


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


@pytest.fixture
def march(accountant, xmas_account, this_year):
    return savings.post_contribution(accountant, account=xmas_account, amount=Decimal("5000"), period=datetime.date(this_year, 3, 1))


class TestReversals:
    def test_reversal_needs_approval_then_cancels_the_entry(self, as_user, accountant, treasurer, xmas_account, march, this_year):
        response = as_user(accountant).post(f"{TXNS}{march.pk}/reverse/", {"reason": "Posted to the wrong member"})
        assert response.status_code == 201, response.data
        reversal = response.data
        assert reversal["txn_type"] == "REVERSAL" and reversal["entry_side"] == "DEBIT"
        assert reversal["status"] == "PENDING"  # reversals are maker-checker by default
        assert reversal["period"] == datetime.date(this_year, 3, 1).isoformat()
        assert ledger.posted_balance(xmas_account) == 5000

        assert code(as_user(accountant).post(f"{TXNS}{march.pk}/reverse/", {"reason": "again"})) == "already_reversed"
        as_user(treasurer).post(f"{TXNS}{reversal['id']}/approve/")

        march.refresh_from_db()
        assert march.status == "REVERSED"
        assert ledger.posted_balance(xmas_account) == 0
        grid = as_user(treasurer).get(f"/api/v1/admin/savings/cycles/{xmas_account.cycle_id}/grid/").data["results"]
        assert grid["totals"][f"{this_year}-03"] == "0.00"
        # March is free again for the correct contribution.
        savings.post_contribution(accountant, account=xmas_account, amount=Decimal("5000"), period=datetime.date(this_year, 3, 1))
        assert AuditLog.objects.filter(action="ledger.entry_reversed", object_id=str(march.pk)).exists()

    def test_creator_cannot_approve_own_reversal(self, as_user, treasurer, march):
        reversal = as_user(treasurer).post(f"{TXNS}{march.pk}/reverse/", {"reason": "Duplicate"}).data
        assert code(as_user(treasurer).post(f"{TXNS}{reversal['id']}/approve/")) == "maker_checker"

    def test_only_posted_reversible_entries(self, as_user, accountant, treasurer, march):
        reversal = as_user(accountant).post(f"{TXNS}{march.pk}/reverse/", {"reason": "Duplicate"}).data
        assert code(as_user(treasurer).post(f"{TXNS}{reversal['id']}/reverse/", {"reason": "x"})) == "not_posted"
        as_user(treasurer).post(f"{TXNS}{reversal['id']}/approve/")
        assert code(as_user(treasurer).post(f"{TXNS}{reversal['id']}/reverse/", {"reason": "x"})) == "not_reversible"

    def test_money_already_paid_out_cannot_be_reversed(self, as_user, accountant, treasurer, regular_account, regular):
        regular.allow_officer_withdrawal = True
        regular.save()
        deposit = savings.post_contribution(accountant, account=regular_account, amount=Decimal("5000"))
        withdrawal = savings.post_withdrawal(treasurer, account=regular_account, amount=Decimal("5000"), reason="Refund")
        ledger.approve_entry(make_officer("Cooperative Chairman"), withdrawal)
        response = as_user(accountant).post(f"{TXNS}{deposit.pk}/reverse/", {"reason": "Wrong"})
        assert code(response) == "insufficient_balance"

    def test_reason_is_required(self, as_user, accountant, march):
        assert code(as_user(accountant).post(f"{TXNS}{march.pk}/reverse/", {})) == "validation_error"


class TestAdjustments:
    def test_credit_adjustment_after_approval(self, as_user, accountant, treasurer, regular_account):
        response = as_user(accountant).post(
            f"{TXNS}adjustments/",
            {"account_type": "SAVINGS", "account": str(regular_account.pk), "entry_side": "CREDIT", "amount": "1500", "reason": "Bank credit not recorded"},
            format="json",
        )
        assert response.status_code == 201, response.data
        assert response.data["status"] == "PENDING"
        assert as_user(accountant).post(f"{TXNS}{response.data['id']}/approve/").status_code == 403  # no approve_transaction
        as_user(treasurer).post(f"{TXNS}{response.data['id']}/approve/")
        assert ledger.posted_balance(regular_account) == Decimal("1500")

    def test_debit_cannot_exceed_the_balance(self, as_user, accountant, regular_account):
        response = as_user(accountant).post(
            f"{TXNS}adjustments/",
            {"account_type": "SAVINGS", "account": str(regular_account.pk), "entry_side": "DEBIT", "amount": "10", "reason": "Fee"},
            format="json",
        )
        assert code(response) == "insufficient_balance"

    def test_self_adjustment_is_refused(self, as_user, accountant, regular):
        own = SavingsAccount.objects.create(member=MemberFactory(user=accountant), product=regular)
        response = as_user(accountant).post(
            f"{TXNS}adjustments/",
            {"account_type": "SAVINGS", "account": str(own.pk), "entry_side": "CREDIT", "amount": "10", "reason": "x"},
            format="json",
        )
        assert code(response) == "self_dealing"


def test_ledger_summary(as_user, accountant, treasurer, march, regular_account):
    savings.post_contribution(accountant, account=regular_account, amount=Decimal("6000"))
    data = as_user(treasurer).get(f"{TXNS}summary/").data
    by_type = {row["txn_type"]: row for row in data["by_type"]}
    assert by_type["SAVINGS_CONTRIBUTION"]["count"] == 2
    assert by_type["SAVINGS_CONTRIBUTION"]["credits"] == "11000.00"
    assert data["entries"] == Transaction.objects.count()
