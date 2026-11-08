"""
Operational paths not covered by the module tests: the demo seeder, department
and settings administration, announcement edits, and the health check.
"""
import pytest
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.configuration.models import CooperativeSettings, Department
from apps.ledger.models import Transaction
from apps.members.models import Member
from apps.notifications.models import Announcement

pytestmark = pytest.mark.django_db


class TestSeedDemo:
    def test_refuses_without_debug(self):
        with override_settings(DEBUG=False), pytest.raises(CommandError, match="DEBUG"):
            call_command("seed_demo", verbosity=0)

    def test_builds_a_consistent_demo_once(self):
        with override_settings(DEBUG=True):
            call_command("seed_demo", verbosity=0)
            members, entries = Member.objects.count(), Transaction.objects.count()
            call_command("seed_demo", verbosity=0)  # second run is a no-op
        assert members >= 5 and entries > 50
        assert (Member.objects.count(), Transaction.objects.count()) == (members, entries)
        # Every seeded entry went through the normal posting rules.
        assert not Transaction.objects.filter(status="POSTED", posted_at__isnull=True).exists()


class TestDepartmentsAndSettings:
    URL = "/api/v1/admin/departments/"

    def test_departments_are_unique_and_audited(self, as_user, super_admin):
        client = as_user(super_admin)
        created = client.post(self.URL, {"name": "Ceramics", "code": "CER"}, format="json")
        assert created.status_code == 201
        assert client.post(self.URL, {"name": "ceramics"}).data["error"]["code"] == "duplicate_name"
        assert client.post(self.URL, {"name": "Glass", "code": "cer"}).data["error"]["code"] == "duplicate_code"
        updated = client.patch(f"{self.URL}{created.data['id']}/", {"is_active": False}, format="json")
        assert updated.data["is_active"] is False
        assert AuditLog.objects.filter(action="department.updated").exists()
        # Unchanged values write no audit noise.
        client.patch(f"{self.URL}{created.data['id']}/", {"is_active": False}, format="json")
        assert AuditLog.objects.filter(action="department.updated").count() == 1

    def test_departments_cannot_be_deleted(self, as_user, super_admin):
        dept = Department.objects.create(name="Polymers")
        # No delete route: unmapped actions are refused before the method is even considered.
        assert as_user(super_admin).delete(f"{self.URL}{dept.pk}/").status_code in (403, 405)
        assert Department.objects.filter(pk=dept.pk).exists()

    def test_settings_validation_and_audit(self, as_user, super_admin, secretary):
        url = "/api/v1/admin/settings/"
        assert as_user(secretary).get(url).status_code == 200  # any officer may read
        assert as_user(secretary).patch(url, {"loan_overdue_grace_days": 3}).status_code == 403
        bad = as_user(super_admin).patch(url, {"membership_number_format": "EMDI/{year}"})
        assert bad.data["error"]["fields"]["membership_number_format"]
        ok = as_user(super_admin).patch(url, {"loan_overdue_grace_days": 3, "membership_number_format": "EMDI/{year}/{seq:05d}"})
        assert ok.status_code == 200 and CooperativeSettings.load().loan_overdue_grace_days == 3
        log = AuditLog.objects.get(action="settings.updated")
        assert "loan_overdue_grace_days" in log.changes


class TestAnnouncementEdits:
    def test_edit_records_changes_and_checks_dates(self, as_user, secretary):
        url = "/api/v1/admin/announcements/"
        created = as_user(secretary).post(url, {"title": "Office hours", "body": "9 to 4"}).data
        changed = as_user(secretary).patch(f"{url}{created['id']}/", {"body": "9 to 5", "is_important": True}).data
        assert changed["body"] == "9 to 5" and changed["is_important"] is True
        log = AuditLog.objects.get(action="announcement.updated")
        assert set(log.changes) == {"body", "is_important"}
        before = timezone.now() - timezone.timedelta(days=1)
        bad = as_user(secretary).patch(f"{url}{created['id']}/", {"expires_at": before.isoformat()})
        assert bad.status_code == 400
        assert as_user(secretary).patch(f"{url}{created['id']}/", {"title": "  "}).status_code == 400
        assert Announcement.objects.get(pk=created["id"]).title == "Office hours"


def test_health_check_needs_no_login(api):
    response = api.get("/api/v1/health/")
    assert response.status_code == 200 and response.data["status"] == "ok"


def test_form_encoded_requests_are_refused_outside_upload_endpoints(as_user, super_admin):
    """Form encodings send a missing boolean as False; only file uploads accept them."""
    client = as_user(super_admin)
    response = client.post("/api/v1/admin/departments/", {"name": "Glass"}, format="multipart")
    assert response.status_code == 415
    assert client.post("/api/v1/admin/departments/", {"name": "Glass"}).status_code == 201
