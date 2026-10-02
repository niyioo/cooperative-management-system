import pytest
from django.conf import settings as django_settings
from django.test import Client

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.configuration.models import CooperativeSettings, Department
from tests.factories import make_officer

pytestmark = pytest.mark.django_db

LOGS = "/api/v1/admin/audit-logs/"
SETTINGS = "/api/v1/admin/settings/"


def code(response):
    return response.data["error"]["code"]


class TestAuditLogApi:
    def test_only_holders_of_view_audit_log(self, as_user, treasurer):
        auditor = make_officer("Auditor")
        assert as_user(auditor).get(LOGS).status_code == 200
        assert as_user(treasurer).get(LOGS).status_code == 403
        denied = AuditLog.objects.get(action="security.access_denied")
        assert denied.actor == treasurer and denied.metadata["path"] == LOGS

    def test_filters(self, as_user, super_admin, secretary):
        client = as_user(secretary)
        member_id = client.post(
            "/api/v1/admin/members/", {"first_name": "Ada", "last_name": "Obi", "phone": "08031234567"}, format="json"
        ).data["id"]
        client.patch(f"/api/v1/admin/members/{member_id}/", {"last_name": "Okafor"}, format="json")

        auditor = as_user(make_officer("Auditor"))
        by_prefix = auditor.get(LOGS, {"action": "member."}).data["results"]
        assert [e["action"] for e in by_prefix] == ["member.updated", "member.created"]
        by_object = auditor.get(LOGS, {"object_type": "members.member", "object_id": member_id}).data["results"]
        assert by_object[0]["changes"] == {"last_name": ["Obi", "Okafor"]}
        assert by_object[0]["actor_repr"] == secretary.email
        assert "member.created" in auditor.get(f"{LOGS}actions/", {"prefix": "member."}).data

    def test_members_probing_officer_endpoints_are_logged(self, as_user, member):
        as_user(member.user).get("/api/v1/admin/members/")
        assert AuditLog.objects.filter(action="security.access_denied", actor=member.user).exists()


class TestSupportConsoleChanges:
    def test_django_admin_edits_are_audited(self):
        root = User.objects.create_superuser(email="root@example.com", password="Root-Password-1", first_name="Root", last_name="Admin")
        department = Department.objects.create(name="Metallurgy", code="MET")
        client = Client()
        client.force_login(root)
        url = f"/{django_settings.DJANGO_ADMIN_URL}configuration/department/{department.pk}/change/"
        response = client.post(url, {"name": "Metallurgical Engineering", "code": "MET", "is_active": "on"})
        assert response.status_code == 302

        log = AuditLog.objects.get(action="admin.configuration.department.updated")
        assert log.actor == root
        assert log.changes == {"name": ["Metallurgy", "Metallurgical Engineering"]}
        assert log.metadata["via"] == "support_console"


class TestSettingsApi:
    def test_any_officer_reads_only_settings_managers_change(self, as_user, treasurer):
        loan_officer = make_officer("Loan Officer")
        data = as_user(loan_officer).get(SETTINGS).data
        assert data["name"] == "EMDI Cooperative Society"
        assert "SAVINGS_WITHDRAWAL" in data["maker_checker_types"]
        assert as_user(treasurer).patch(SETTINGS, {"loan_overdue_grace_days": 3}, format="json").status_code == 403

    def test_update_is_audited(self, as_user, super_admin):
        response = as_user(super_admin).patch(
            SETTINGS,
            {"loan_overdue_grace_days": 3, "maker_checker_types": ["ADJUSTMENT", "REVERSAL", "SAVINGS_CONTRIBUTION"]},
            format="json",
        )
        assert response.status_code == 200, response.data
        assert response.data["maker_checker_types"] == ["ADJUSTMENT", "REVERSAL", "SAVINGS_CONTRIBUTION"]
        assert CooperativeSettings.load().loan_overdue_grace_days == 3
        log = AuditLog.objects.get(action="settings.updated")
        assert log.changes["loan_overdue_grace_days"] == [7, 3]

    def test_validation(self, as_user, super_admin):
        client = as_user(super_admin)
        assert code(client.patch(SETTINGS, {"membership_number_format": "EMDI/COOP"}, format="json")) == "invalid_format"
        assert code(client.patch(SETTINGS, {"maker_checker_types": ["TELEPORT"]}, format="json")) == "validation_error"
