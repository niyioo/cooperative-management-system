import datetime
from decimal import Decimal

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts import services as account_services
from apps.accounts.perms import P
from apps.audit.models import AuditLog
from apps.configuration.models import Department
from apps.ledger.models import Transaction
from apps.members.models import Member, MemberDocument, NextOfKin
from apps.savings.models import SavingsAccount, SavingsCycle, SavingsProduct
from tests.factories import MemberFactory, make_officer

from .helpers import disguised_file, pdf_file, png_file

pytestmark = pytest.mark.django_db

MEMBERS = "/api/v1/admin/members/"


def code(response):
    return response.data["error"]["code"]


def member_url(member, suffix=""):
    return f"{MEMBERS}{member.pk}/{suffix}"


NEW_MEMBER = {
    "first_name": "Bisi",
    "last_name": "Adeyemi",
    "phone": "0803 123 4567",
    "email": "Bisi.Adeyemi@example.com",
    "staff_number": "emdi/0101",
    "next_of_kin": {"full_name": "Tunde Adeyemi", "relationship": "Brother", "phone": "08030000000"},
}


class TestRegistration:
    def test_register_member(self, as_user, secretary, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            response = as_user(secretary).post(MEMBERS, NEW_MEMBER, format="json")

        assert response.status_code == 201, response.data
        data = response.data
        assert data["membership_number"].startswith("EMDI/COOP/")
        assert data["status"] == "PENDING"
        assert data["email"] == "bisi.adeyemi@example.com"
        assert data["phone"] == "08031234567"
        assert data["next_of_kin"][0]["is_primary"] is True
        assert data["portal"] == {
            "has_email": True,
            "activated": False,
            "is_active": True,
            "must_change_password": False,
            "last_login": None,
        }
        member = Member.objects.get(pk=data["id"])
        assert SavingsAccount.objects.filter(member=member, product__code="REGULAR").exists()
        assert member.status_changes.count() == 1
        assert len(mail.outbox) == 1 and "Activate" in mail.outbox[0].subject
        assert AuditLog.objects.filter(action="member.created", object_id=str(member.pk)).exists()

    def test_member_without_email_signs_in_with_membership_number(self, api, as_user, secretary):
        response = as_user(secretary).post(MEMBERS, {**NEW_MEMBER, "email": ""}, format="json")
        assert response.status_code == 201
        assert response.data["email"] is None
        assert response.data["portal"]["has_email"] is False
        assert len(mail.outbox) == 0

        member = Member.objects.get(pk=response.data["id"])
        temp = as_user(secretary).post(member_url(member, "temporary-password/")).data["temporary_password"]
        api.credentials()
        login = api.post("/api/v1/auth/login/", {"identifier": member.membership_number, "password": temp}, format="json")
        assert login.status_code == 200
        assert login.data["user"]["must_change_password"] is True

    def test_activation_email_needs_an_address(self, as_user, secretary):
        member = Member.objects.get(pk=as_user(secretary).post(MEMBERS, {**NEW_MEMBER, "email": ""}, format="json").data["id"])
        assert code(as_user(secretary).post(member_url(member, "send-activation/"))) == "no_email"

    def test_registering_as_active_needs_status_permission(self, as_user, super_admin):
        account_services.create_role(super_admin, name="Registrar", permissions=[P.ADD_MEMBER, P.VIEW_MEMBER])
        registrar = make_officer("Registrar")
        response = as_user(registrar).post(MEMBERS, {**NEW_MEMBER, "status": "ACTIVE"}, format="json")
        assert response.status_code == 403

    def test_manual_membership_number_is_unique_case_insensitively(self, as_user, secretary):
        client = as_user(secretary)
        first = client.post(MEMBERS, {**NEW_MEMBER, "membership_number": "EMDI/OLD/0007"}, format="json")
        assert first.data["membership_number"] == "EMDI/OLD/0007"
        again = client.post(
            MEMBERS, {**NEW_MEMBER, "email": "x@example.com", "staff_number": "", "membership_number": "emdi/old/0007"},
            format="json",
        )
        assert code(again) == "duplicate_membership_number"

    def test_duplicate_staff_number_is_rejected(self, as_user, secretary):
        client = as_user(secretary)
        client.post(MEMBERS, NEW_MEMBER, format="json")
        again = client.post(MEMBERS, {**NEW_MEMBER, "email": "other@example.com", "staff_number": "EMDI/0101"}, format="json")
        assert code(again) == "duplicate_staff_number"

    def test_duplicate_member_email_is_rejected(self, as_user, secretary):
        client = as_user(secretary)
        client.post(MEMBERS, NEW_MEMBER, format="json")
        again = client.post(MEMBERS, {**NEW_MEMBER, "staff_number": ""}, format="json")
        assert code(again) == "duplicate_email"

    def test_existing_officer_account_gets_a_member_profile(self, as_user, secretary, treasurer):
        response = as_user(secretary).post(MEMBERS, {**NEW_MEMBER, "email": treasurer.email}, format="json")
        assert response.status_code == 201
        treasurer.refresh_from_db()
        assert treasurer.member.pk == Member.objects.get(pk=response.data["id"]).pk

    def test_invalid_values_are_rejected(self, as_user, secretary):
        response = as_user(secretary).post(
            MEMBERS, {**NEW_MEMBER, "phone": "abc", "bank_account_number": "123"}, format="json"
        )
        assert code(response) == "validation_error"
        assert {"phone", "bank_account_number"} <= set(response.data["error"]["fields"])


class TestProfileChanges:
    def test_update_is_audited_and_synced_to_the_login(self, as_user, secretary, member):
        response = as_user(secretary).patch(
            member_url(member), {"last_name": "Okonkwo", "bank_account_number": "0123456789"}, format="json"
        )
        assert response.status_code == 200
        member.user.refresh_from_db()
        assert member.user.last_name == "Okonkwo"
        log = AuditLog.objects.get(action="member.updated")
        assert set(log.changes) == {"last_name", "bank_account_number"}

    def test_officer_cannot_edit_own_member_record(self, as_user, secretary):
        own = MemberFactory(user=secretary)
        response = as_user(secretary).patch(member_url(own), {"last_name": "Changed"}, format="json")
        assert code(response) == "self_dealing"

    def test_status_transitions(self, as_user, secretary):
        member = MemberFactory(status=Member.Status.PENDING)
        client = as_user(secretary)
        assert client.post(member_url(member, "activate/")).data["status"] == "ACTIVE"
        assert code(client.post(member_url(member, "suspend/"))) == "reason_required"
        assert client.post(member_url(member, "suspend/"), {"reason": "Pending inquiry"}).data["status"] == "SUSPENDED"
        assert code(client.post(member_url(member, "activate/"))) == "invalid_transition"
        assert client.post(member_url(member, "reinstate/")).data["status"] == "ACTIVE"
        history = client.get(member_url(member)).data["status_history"]
        assert [h["to_status"] for h in history[:3]] == ["ACTIVE", "SUSPENDED", "ACTIVE"]

    def test_closed_membership_is_read_only(self, as_user, secretary, member):
        Member.objects.filter(pk=member.pk).update(status=Member.Status.CLOSED, closed_at=timezone.now())
        assert code(as_user(secretary).patch(member_url(member), {"last_name": "X"}, format="json")) == "member_closed"

    def test_list_search_and_filter(self, as_user, secretary):
        MemberFactory(first_name="Ngozi", staff_number="EMDI/7777")
        MemberFactory(status=Member.Status.SUSPENDED)
        client = as_user(secretary)
        assert client.get(MEMBERS, {"search": "7777"}).data["count"] == 1
        assert client.get(MEMBERS, {"status": "SUSPENDED"}).data["count"] == 1
        assert client.get(MEMBERS).data["count"] == 2

    def test_member_user_cannot_use_officer_api(self, as_user, member):
        assert as_user(member.user).get(MEMBERS).status_code == 403


class TestFinancialViews:
    def _post(self, member, account, amount, *, status="POSTED", period=None, officer=None):
        return Transaction.objects.create(
            member=member,
            txn_type="SAVINGS_CONTRIBUTION",
            entry_side="CREDIT",
            amount=Decimal(amount),
            savings_account=account,
            period=period,
            status=status,
            posted_at=timezone.now() if status == "POSTED" else None,
            created_by=officer,
        )

    def test_summary_is_derived_from_the_ledger(self, as_user, treasurer, member):
        regular = SavingsAccount.objects.create(member=member, product=SavingsProduct.objects.get(code="REGULAR"))
        year = timezone.localdate().year
        cycle = SavingsCycle.objects.create(
            product=SavingsProduct.objects.get(code="CHRISTMAS"),
            year=year,
            start_date=datetime.date(year, 1, 1),
            end_date=datetime.date(year, 10, 31),
        )
        christmas = SavingsAccount.objects.create(member=member, product=cycle.product, cycle=cycle)
        self._post(member, christmas, "3000", period=datetime.date(year, 1, 1), officer=treasurer)
        self._post(member, christmas, "2000", period=datetime.date(year, 2, 1), officer=treasurer)
        self._post(member, regular, "2000", officer=treasurer)
        self._post(member, regular, "9999", status="PENDING", officer=treasurer)  # not yet approved

        savings = as_user(treasurer).get(member_url(member, "financial-summary/")).data["savings"]
        assert savings["christmas"]["balance"] == "5000.00"
        assert savings["other"]["balance"] == "2000.00"
        assert savings["total"] == "7000.00"

    def test_sections_follow_the_viewers_permissions(self, as_user, secretary, treasurer, member):
        assert as_user(secretary).get(member_url(member, "financial-summary/")).data == {}
        assert set(as_user(treasurer).get(member_url(member, "financial-summary/")).data) == {
            "savings",
            "loans",
            "investments",
            "dividends",
        }

    def test_transactions_need_the_ledger_permission(self, as_user, secretary, treasurer, member):
        account = SavingsAccount.objects.create(member=member, product=SavingsProduct.objects.get(code="REGULAR"))
        self._post(member, account, "1500", officer=treasurer)
        assert as_user(secretary).get(member_url(member, "transactions/")).status_code == 403
        response = as_user(treasurer).get(member_url(member, "transactions/"))
        assert response.status_code == 200
        assert response.data["results"][0]["type_label"] == "Regular Savings contribution"


class TestDocumentsPhotoAndNextOfKin:
    def test_document_lifecycle(self, as_user, secretary, treasurer, member):
        client = as_user(secretary)
        response = client.post(
            member_url(member, "documents/"), {"document_type": "ID_CARD", "title": "NIN slip", "file": pdf_file()}, format="multipart"
        )
        assert response.status_code == 201, response.data
        document = MemberDocument.objects.get(pk=response.data["id"])

        download = as_user(treasurer).get(member_url(member, f"documents/{document.pk}/download/"))
        assert download.status_code == 200
        assert b"".join(download.streaming_content).startswith(b"%PDF")
        assert AuditLog.objects.filter(action="member.document_downloaded").exists()

        client = as_user(secretary)
        assert client.post(member_url(member, f"documents/{document.pk}/verify/")).status_code == 200
        assert code(client.delete(member_url(member, f"documents/{document.pk}/"))) == "document_verified"

    def test_disguised_file_is_rejected(self, as_user, secretary, member):
        response = as_user(secretary).post(
            member_url(member, "documents/"), {"document_type": "OTHER", "file": disguised_file()}, format="multipart"
        )
        assert response.status_code == 400
        assert "file" in response.data["error"]["fields"]

    def test_unverified_document_can_be_removed(self, as_user, secretary, member):
        client = as_user(secretary)
        doc_id = client.post(
            member_url(member, "documents/"), {"document_type": "OTHER", "file": pdf_file()}, format="multipart"
        ).data["id"]
        assert client.delete(member_url(member, f"documents/{doc_id}/")).status_code == 204
        assert not MemberDocument.objects.filter(pk=doc_id).exists()

    def test_member_cannot_download_documents_through_officer_api(self, as_user, member):
        assert as_user(member.user).get(member_url(member, "documents/")).status_code == 403

    def test_photo_upload_and_fetch(self, as_user, secretary, member):
        client = as_user(secretary)
        response = client.put(member_url(member, "photo/"), {"photo": png_file()}, format="multipart")
        assert response.status_code == 200
        assert response.data["has_photo"] is True
        photo = client.get(member_url(member, "photo/"))
        assert b"".join(photo.streaming_content).startswith(b"\x89PNG")

    def test_new_primary_next_of_kin_replaces_the_old_one(self, as_user, secretary, member):
        client = as_user(secretary)
        first = client.post(member_url(member, "next-of-kin/"), {"full_name": "A", "relationship": "Sister", "phone": "08010000000"}).data
        assert first["is_primary"] is True
        second = client.post(
            member_url(member, "next-of-kin/"),
            {"full_name": "B", "relationship": "Spouse", "phone": "08020000000", "is_primary": True},
        ).data
        assert NextOfKin.objects.get(pk=first["id"]).is_primary is False
        assert client.delete(member_url(member, f"next-of-kin/{second['id']}/")).status_code == 204


class TestDepartments:
    def test_any_officer_can_list_but_only_settings_managers_create(self, as_user, secretary, super_admin):
        Department.objects.create(name="Metallurgy", code="MET")
        assert as_user(secretary).get("/api/v1/admin/departments/").data["count"] == 1
        assert as_user(secretary).post("/api/v1/admin/departments/", {"name": "Ceramics"}).status_code == 403
        response = as_user(super_admin).post("/api/v1/admin/departments/", {"name": "Ceramics", "code": "cer"})
        assert response.status_code == 201
        assert response.data["code"] == "CER"
        duplicate = as_user(super_admin).post("/api/v1/admin/departments/", {"name": "ceramics"})
        assert code(duplicate) == "duplicate_name"
