import datetime
import io

import pytest
from openpyxl import load_workbook

from apps.audit.models import AuditLog
from apps.common.exceptions import DomainError
from apps.ledger import services as ledger
from apps.ledger.models import Transaction, TransactionBatch
from apps.members.models import Member
from apps.members.tests.helpers import xlsx_file
from apps.savings import services as savings
from apps.savings.models import SavingsAccount, SavingsCycle
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db

BATCHES = "/api/v1/admin/batches/"
HEADER = ["Membership number", "Name", "Amount", "Reference"]


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def savers(db, this_year):
    joined = datetime.date(this_year - 1, 1, 1)
    return [MemberFactory(date_joined=joined, last_name=name) for name in ("Adebayo", "Bello", "Chukwu")]


def upload(client, rows, *, batch_type="CONTRIBUTIONS", product="CHRISTMAS", period=None, header=HEADER):
    data = {"batch_type": batch_type, "file": xlsx_file(header, rows), "description": "Payroll"}
    if product:
        data["product"] = product
    if period:
        data["period"] = period
    return client.post(BATCHES, data, format="multipart")


def balance(account):
    return ledger.posted_balance(account)


class TestContributionBatches:
    def test_payroll_batch_posts_only_after_a_second_officer_approves(
        self, as_user, accountant, treasurer, open_cycle, savers, this_year
    ):
        rows = [[m.membership_number, m.full_name, 5000, "PAY-MAR"] for m in savers[:2]]
        response = upload(as_user(accountant), rows, period=f"{this_year}-03")
        assert response.status_code == 201, response.data
        batch = response.data
        assert batch["status"] == "VALIDATED", batch["validation_report"]
        assert batch["line_count"] == 2
        assert batch["total_amount"] == "10000.00"

        account = SavingsAccount.objects.get(member=savers[0], cycle=open_cycle)
        assert balance(account) == 0  # lines are pending until approval

        client = as_user(accountant)
        assert client.post(f"{BATCHES}{batch['id']}/submit/").data["status"] == "SUBMITTED"
        assert client.post(f"{BATCHES}{batch['id']}/approve/").status_code == 403  # no approve_batch

        approved = as_user(treasurer).post(f"{BATCHES}{batch['id']}/approve/")
        assert approved.data["status"] == "POSTED"
        assert balance(account) == 5000
        entry = Transaction.objects.get(savings_account=account)
        assert entry.approved_by == treasurer and entry.period == datetime.date(this_year, 3, 1)
        assert AuditLog.objects.filter(action="batch.posted").exists()

    def test_preparer_cannot_approve_their_own_batch(self, as_user, treasurer, open_cycle, savers, this_year):
        batch = upload(as_user(treasurer), [[savers[0].membership_number, "", 5000, ""]], period=f"{this_year}-03").data
        as_user(treasurer).post(f"{BATCHES}{batch['id']}/submit/")
        assert code(as_user(treasurer).post(f"{BATCHES}{batch['id']}/approve/")) == "maker_checker"

    def test_row_errors_are_reported_and_nothing_is_created(self, as_user, accountant, open_cycle, savers, this_year):
        savings.post_contribution(
            accountant, account=SavingsAccount.objects.get_or_create(member=savers[2], cycle=open_cycle, defaults={"product": open_cycle.product})[0],
            amount=5000, period=datetime.date(this_year, 3, 1),
        )
        rows = [
            ["EMDI/NOPE/1", "Ghost", 5000, ""],
            [savers[0].membership_number, "", "abc", ""],
            [savers[1].membership_number, "", 5000, ""],
            [savers[1].membership_number, "", 5000, ""],
            [savers[2].membership_number, "", 5000, ""],
        ]
        batch = upload(as_user(accountant), rows, period=f"{this_year}-03").data
        assert batch["status"] == "DRAFT"
        errors = {e["row"]: e["errors"] for e in batch["validation_report"]["errors"]}
        assert "membership_number" in errors[2]
        assert "amount" in errors[3]
        assert "Duplicate of row 4" in errors[5]["amount"][0]
        assert "already been recorded" in errors[6]["amount"][0]
        assert batch["line_count"] == 0
        assert not Transaction.objects.filter(batch_id=batch["id"]).exists()

    def test_missing_identifier_column(self, as_user, accountant, open_cycle, this_year):
        batch = upload(as_user(accountant), [["Ada", 5000]], header=["Name", "Amount"], period=f"{this_year}-03").data
        assert "identifies members" in batch["validation_report"]["file_errors"][0]

    def test_changes_after_upload_are_caught(self, as_user, accountant, treasurer, open_cycle, savers, this_year):
        batch = upload(as_user(accountant), [[savers[0].membership_number, "", 5000, ""]], period=f"{this_year}-03").data
        as_user(accountant).post(f"{BATCHES}{batch['id']}/submit/")
        account = SavingsAccount.objects.get(member=savers[0], cycle=open_cycle)

        # A pending batch line already claims March, so a hand-posted duplicate is refused…
        with pytest.raises(DomainError):
            savings.post_contribution(accountant, account=account, amount=5000, period=datetime.date(this_year, 3, 1))

        # …and a member deactivated after upload blocks the whole batch at approval.
        Member.objects.filter(pk=savers[0].pk).update(status=Member.Status.INACTIVE)
        response = as_user(treasurer).post(f"{BATCHES}{batch['id']}/approve/")
        assert code(response) == "batch_conflicts"
        assert TransactionBatch.objects.get(pk=batch["id"]).status == "SUBMITTED"

    def test_rejecting_a_batch(self, as_user, accountant, treasurer, open_cycle, savers, this_year):
        batch = upload(as_user(accountant), [[savers[0].membership_number, "", 5000, ""]], period=f"{this_year}-03").data
        as_user(accountant).post(f"{BATCHES}{batch['id']}/submit/")
        response = as_user(treasurer).post(f"{BATCHES}{batch['id']}/reject/", {"reason": "Wrong month"})
        assert response.data["status"] == "REJECTED"
        assert set(Transaction.objects.filter(batch_id=batch["id"]).values_list("status", flat=True)) == {"REJECTED"}

    def test_template(self, as_user, accountant):
        response = as_user(accountant).get(f"{BATCHES}template/", {"type": "CONTRIBUTIONS"})
        headers = [c.value for c in load_workbook(io.BytesIO(response.content))["Contributions"][1]]
        assert "Amount *" in headers


class TestOpeningBalances:
    def test_regular_savings_opening_balances(self, as_user, accountant, treasurer, savers, regular, christmas):
        rows = [
            [savers[0].membership_number, "REGULAR", "125,000.00"],
            [savers[1].membership_number, "CHRISTMAS", 5000],
        ]
        header = ["Membership number", "Product code", "Amount"]
        batch = upload(as_user(accountant), rows, batch_type="OPENING_BALANCES", product=None, header=header).data
        errors = {e["row"]: e["errors"] for e in batch["validation_report"]["errors"]}
        assert "monthly contributions" in errors[3]["product"][0]

        batch = upload(as_user(accountant), rows[:1], batch_type="OPENING_BALANCES", product=None, header=header).data
        assert batch["status"] == "VALIDATED"
        as_user(accountant).post(f"{BATCHES}{batch['id']}/submit/")
        as_user(treasurer).post(f"{BATCHES}{batch['id']}/approve/")
        assert balance(SavingsAccount.objects.get(member=savers[0], product=regular)) == 125000

        again = upload(as_user(accountant), rows[:1], batch_type="OPENING_BALANCES", product=None, header=header).data
        assert "already has" in again["validation_report"]["errors"][0]["errors"]["amount"][0]


class TestCyclePayout:
    def test_payout_empties_the_cycle(self, as_user, accountant, treasurer, open_cycle, savers, this_year):
        for member, amount in ((savers[0], 5000), (savers[1], 7000)):
            account = SavingsAccount.objects.get_or_create(member=member, cycle=open_cycle, defaults={"product": open_cycle.product})[0]
            savings.post_contribution(accountant, account=account, amount=amount, period=datetime.date(this_year, 3, 1))

        cycles = "/api/v1/admin/savings/cycles/"
        assert code(as_user(treasurer).post(f"{cycles}{open_cycle.pk}/payout/")) == "invalid_cycle_status"
        as_user(treasurer).post(f"{cycles}{open_cycle.pk}/close/")

        batch = as_user(treasurer).post(f"{cycles}{open_cycle.pk}/payout/").data
        assert batch["batch_type"] == "CYCLE_PAYOUTS"
        assert batch["line_count"] == 2 and batch["total_amount"] == "12000.00"
        assert code(as_user(treasurer).post(f"{cycles}{open_cycle.pk}/payout/")) == "payout_in_progress"

        as_user(treasurer).post(f"{BATCHES}{batch['id']}/submit/")
        chairman = make_officer("Cooperative Chairman")  # holds approve_batch; the treasurer prepared it
        assert as_user(chairman).post(f"{BATCHES}{batch['id']}/approve/").data["status"] == "POSTED"

        open_cycle.refresh_from_db()
        assert open_cycle.status == SavingsCycle.Status.PAID_OUT
        accounts = SavingsAccount.objects.filter(cycle=open_cycle)
        assert all(a.status == SavingsAccount.Status.CLOSED for a in accounts)
        assert all(balance(a) == 0 for a in accounts)

        grid = as_user(treasurer).get(f"{cycles}{open_cycle.pk}/grid/").data["results"]
        assert grid["totals"]["total"] == "12000.00"  # contributions stay visible
        assert grid["totals"]["paid_out"] == "12000.00"


def test_batch_lists_need_batch_permissions(as_user, secretary):
    assert as_user(secretary).get(BATCHES).status_code == 403
    assert TransactionBatch.objects.count() == 0
