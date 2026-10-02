import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group, Permission
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.ledger.models import Transaction
from apps.members.models import MemberStatus
from apps.reports import definitions  # noqa: F401
from apps.reports.engine import REGISTRY
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/reports/"
D = Decimal


def post(member, account, amount, txn_type="SAVINGS_CONTRIBUTION", value_date=None, side="CREDIT", **extra):
    return Transaction.objects.create(
        member=member, savings_account=account, txn_type=txn_type, entry_side=side, amount=D(amount), status="POSTED",
        posted_at=timezone.now(), value_date=value_date or timezone.localdate(), **extra,
    )


@pytest.fixture
def saver(regular):
    member = MemberFactory()
    account = SavingsAccount.objects.create(member=member, product=regular)
    post(member, account, "10000", "SAVINGS_OPENING_BALANCE", value_date=datetime.date(2026, 1, 2))
    post(member, account, "2500", value_date=datetime.date(2026, 3, 25))
    return member, account


def viewer_without_export():
    group, _ = Group.objects.get_or_create(name="Report Viewer")
    group.permissions.set(Permission.objects.filter(
        content_type__app_label__in=["reports", "members"], codename__in=["view_reports", "view_member"]))
    return make_officer("Report Viewer")


class TestCatalogue:
    def test_lists_only_reports_the_role_may_run(self, as_user, secretary, treasurer):
        secretary_keys = {r["key"] for r in as_user(secretary).get(URL).data}
        assert secretary_keys == {"members", "account-closures"}
        treasurer_keys = {r["key"] for r in as_user(treasurer).get(URL).data}
        assert set(REGISTRY) == treasurer_keys

    def test_report_permissions_are_enforced_server_side(self, as_user, secretary):
        assert as_user(secretary).get(f"{URL}transactions/").status_code == 403
        assert as_user(secretary).get(f"{URL}no-such-report/").status_code == 404

    def test_needs_view_reports(self, as_user):
        loan_only = make_officer()
        assert as_user(loan_only).get(URL).status_code == 403


class TestRunning:
    def test_savings_balances_as_at_a_date(self, as_user, treasurer, saver):
        member, account = saver
        data = as_user(treasurer).get(f"{URL}savings/", {"as_at": "2026-02-28"}).data
        row = next(r for r in data["rows"] if r["account_number"] == account.account_number)
        assert row["balance"] == "10000.00"  # the March contribution is after the date
        data = as_user(treasurer).get(f"{URL}savings/", {"as_at": "2026-03-31"}).data
        assert data["totals"]["balance"] == "12500.00"
        assert {"label": "Balances as at", "value": "31 Mar 2026"} in data["filters"]

    def test_member_filters_and_summary(self, as_user, treasurer):
        MemberFactory(status=MemberStatus.ACTIVE)
        MemberFactory(status=MemberStatus.SUSPENDED)
        data = as_user(treasurer).get(f"{URL}members/", {"status": "SUSPENDED"}).data
        assert data["total_rows"] == 1 and data["rows"][0]["status"] == "Suspended"
        assert data["summary"][0] == {"label": "Members", "value": 1, "kind": "int"}

    def test_invalid_filters_are_rejected(self, as_user, treasurer):
        response = as_user(treasurer).get(f"{URL}members/", {"status": "NOPE"})
        assert response.status_code == 400 and "status" in response.data["error"]["fields"]
        response = as_user(treasurer).get(f"{URL}transactions/", {"date_from": "2026-05-01", "date_to": "2026-01-01"})
        assert "date_to" in response.data["error"]["fields"]

    def test_member_statement_requires_a_member_and_is_audited(self, as_user, treasurer, saver):
        member, _ = saver
        assert "member" in as_user(treasurer).get(f"{URL}member-statement/").data["error"]["fields"]
        data = as_user(treasurer).get(f"{URL}member-statement/", {"member": member.pk}).data
        assert data["total_rows"] == 2 and data["totals"]["credit"] == "12500.00"
        assert AuditLog.objects.filter(action="report.viewed").exists()

    def test_transactions_report_includes_reversals_and_totals(self, as_user, treasurer, saver):
        member, account = saver
        original = Transaction.objects.filter(member=member, txn_type="SAVINGS_CONTRIBUTION").get()
        post(member, account, "2500", "REVERSAL", side="DEBIT", reverses=original, value_date=datetime.date(2026, 3, 26))
        Transaction.objects.filter(pk=original.pk).update(status="REVERSED")
        data = as_user(treasurer).get(f"{URL}transactions/", {"member": member.pk}).data
        assert data["total_rows"] == 3
        assert data["totals"] == {"credit": "12500.00", "debit": "2500.00"}

    @pytest.mark.parametrize("key", sorted(REGISTRY))
    def test_every_report_runs_on_an_empty_database(self, as_user, super_admin, key):
        member = MemberFactory()
        params = {"member": member.pk} if key == "member-statement" else {}
        response = as_user(super_admin).get(f"{URL}{key}/", params)
        assert response.status_code == 200, response.data
        assert response.data["columns"] and isinstance(response.data["rows"], list)


class TestExports:
    @pytest.mark.parametrize("fmt,magic", [("xlsx", b"PK"), ("pdf", b"%PDF")])
    def test_exports_return_files_and_are_audited(self, as_user, treasurer, saver, fmt, magic):
        response = as_user(treasurer).get(f"{URL}savings/", {"format": fmt})
        assert response.status_code == 200
        assert response.content[:4].startswith(magic)
        assert response["Content-Disposition"].startswith('attachment; filename="savings-')
        log = AuditLog.objects.get(action="report.exported")
        assert log.metadata["format"] == fmt and log.metadata["report"] == "savings"

    def test_export_needs_export_permission(self, as_user):
        viewer = viewer_without_export()
        assert as_user(viewer).get(f"{URL}members/").status_code == 200
        response = as_user(viewer).get(f"{URL}members/", {"format": "pdf"})
        assert response.status_code == 403
        assert as_user(viewer).get(URL).data[0]["can_export"] is False

    def test_unknown_format(self, as_user, treasurer):
        assert as_user(treasurer).get(f"{URL}members/", {"format": "csv"}).status_code == 400
