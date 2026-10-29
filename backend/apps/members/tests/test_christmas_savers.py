"""Christmas savers (BR-33): non-members who save only in Christmas Savings, with no portal access."""
import datetime
from decimal import Decimal

import pytest
from django.core import mail

from apps.audit.models import AuditLog
from apps.common.exceptions import DomainError
from apps.configuration.models import CooperativeSettings
from apps.investments import services as investments
from apps.investments.models import InvestmentProduct
from apps.loans import services as loans
from apps.loans.eligibility import evaluate
from apps.loans.models import LoanProduct
from apps.members.models import Member
from apps.notifications.services import broadcast_recipients
from apps.savings import services as savings
from apps.savings.models import SavingsAccount, SavingsProduct
from tests.factories import MemberFactory, make_officer

from .helpers import xlsx_file

pytestmark = pytest.mark.django_db
D = Decimal
MEMBERS = "/api/v1/admin/members/"
SAVER = {"first_name": "Kemi", "last_name": "Saver", "phone": "08035550000", "email": "kemi@example.org",
         "staff_number": "EMDI/0999", "membership_type": "CHRISTMAS_SAVER", "status": "ACTIVE"}


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def secretary_admin(db):
    return make_officer("Super Administrator")


@pytest.fixture
def saver(as_user, secretary_admin, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = as_user(secretary_admin).post(MEMBERS, SAVER, format="json")
    assert response.status_code == 201, response.data
    return Member.objects.get(pk=response.data["id"])


class TestRegistration:
    def test_savers_get_their_own_number_series_and_no_member_accounts(self, saver):
        assert saver.membership_number == "EMDI/XMAS/0001"
        assert saver.membership_type == Member.Type.CHRISTMAS_SAVER and not saver.is_full_member
        assert not SavingsAccount.objects.filter(member=saver).exists()  # no Regular Savings
        assert mail.outbox == []  # never invited to the portal
        log = AuditLog.objects.get(action="member.created", object_id=str(saver.pk))
        assert log.metadata["membership_type"] == "CHRISTMAS_SAVER"

    def test_member_numbers_are_unaffected(self, saver, as_user, secretary_admin):
        response = as_user(secretary_admin).post(MEMBERS, {**SAVER, "membership_type": "MEMBER", "email": "", "staff_number": "EMDI/0998"},
                                                 format="json")
        assert response.data["membership_number"].startswith("EMDI/COOP/")
        assert response.data["membership_type_label"] == "Member"

    def test_the_list_can_be_filtered_by_type(self, saver, as_user, secretary_admin):
        MemberFactory()
        rows = as_user(secretary_admin).get(MEMBERS, {"membership_type": "CHRISTMAS_SAVER"}).data["results"]
        assert [r["membership_number"] for r in rows] == [saver.membership_number]

    def test_savers_and_members_need_different_number_formats(self, super_admin):
        from apps.configuration import services as config

        with pytest.raises(DomainError):
            config.update_settings(super_admin, membership_number_format="EMDI/{seq:04d}", saver_number_format="EMDI/{seq:04d}")

    def test_import_can_register_savers(self, as_user, secretary_admin):
        header = ["First name", "Last name", "Phone", "Membership type"]
        upload = xlsx_file(header, [["Ola", "One", "08031110001", "Christmas saver"], ["Ada", "Two", "08031110002", ""]])
        client = as_user(secretary_admin)
        created = client.post(f"{MEMBERS}imports/", {"file": upload}, format="multipart").data
        assert created["status"] == "READY", created["report"]
        client.post(f"{MEMBERS}imports/{created['id']}/commit/", {"send_activation": False}, format="json")
        assert Member.objects.get(first_name="Ola").membership_type == Member.Type.CHRISTMAS_SAVER
        assert Member.objects.get(first_name="Ada").membership_type == Member.Type.MEMBER


class TestNoPortalAccess:
    def test_a_saver_cannot_sign_in_even_with_a_password(self, api, saver, password):
        saver.user.set_password(password)
        saver.user.save()
        response = api.post("/api/v1/auth/login/", {"identifier": saver.membership_number, "password": password}, format="json")
        assert response.status_code == 401
        assert response.data["error"]["code"] == "invalid_credentials"  # same answer as a wrong password

    def test_officers_cannot_invite_a_saver(self, as_user, secretary_admin, saver):
        client = as_user(secretary_admin)
        assert code(client.post(f"{MEMBERS}{saver.pk}/send-activation/")) == "no_portal_access"
        assert code(client.post(f"{MEMBERS}{saver.pk}/temporary-password/")) == "no_portal_access"


class TestChristmasSavingsOnly:
    def test_opening_the_cycle_gives_savers_an_account_and_they_can_contribute(self, saver, open_cycle, accountant):
        account = SavingsAccount.objects.get(member=saver, cycle=open_cycle)
        entry = savings.post_contribution(accountant, account=account, amount=D("5000"), period=open_cycle.start_date)
        assert entry.status == "POSTED"

    def test_regular_savings_are_refused(self, saver, accountant, regular):
        with pytest.raises(DomainError) as refused:
            savings.open_account(accountant, member=saver, product=regular)
        assert "Christmas saver" in str(refused.value)
        account = SavingsAccount(member=saver, product=regular)
        from apps.savings.rules import contribution_problems

        assert any("Christmas saver" in p for p in contribution_problems(account, D("5000"), None))

    def test_only_christmas_is_open_to_non_members_by_default(self):
        assert list(SavingsProduct.objects.filter(open_to_non_members=True).values_list("code", flat=True)) == ["CHRISTMAS"]


class TestMembersOnlyFeatures:
    def test_savers_cannot_borrow_guarantee_or_invest(self, saver, super_admin):
        product = LoanProduct.objects.create(name="Loan", code="LN", interest_rate=D("10"), min_amount=D("1000"),
                                             max_amount=D("100000"), min_term_months=1, max_term_months=12)
        result = evaluate(saver, product, amount=D("5000"), term_months=6)
        assert not result["eligible"]
        assert next(c for c in result["checks"] if c["code"] == "full_member")["passed"] is False

        borrower = MemberFactory(date_joined=datetime.date(2020, 1, 1))
        application = loans.create_application(super_admin, member=borrower, product=product, amount_requested=D("5000"),
                                               term_months=6, purpose="x")
        with pytest.raises(DomainError):
            loans.add_guarantor(super_admin, application, saver.membership_number)

        shares = InvestmentProduct.objects.create(name="Shares", code="SH", min_amount=D("1000"))
        with pytest.raises(DomainError) as refused:
            investments.open_account(super_admin, member=saver, product=shares)
        assert "cannot invest" in str(refused.value)

    def test_broadcasts_and_member_counts_leave_savers_out(self, saver, as_user, secretary_admin):
        member = MemberFactory()
        assert list(broadcast_recipients(audience="ALL_ACTIVE")) == [member]
        counts = as_user(secretary_admin).get("/api/v1/admin/dashboard/").data["members"]
        assert counts["total"] == 1 and counts["christmas_savers"] == 1


class TestBecomingAMember:
    def test_conversion_keeps_the_record_and_christmas_history(self, as_user, secretary_admin, saver, open_cycle, accountant):
        christmas = SavingsAccount.objects.get(member=saver, cycle=open_cycle)
        savings.post_contribution(accountant, account=christmas, amount=D("5000"), period=open_cycle.start_date)

        response = as_user(secretary_admin).post(f"{MEMBERS}{saver.pk}/convert-to-member/", {"reason": "Joined at the AGM"}, format="json")
        assert response.status_code == 200, response.data
        saver.refresh_from_db()
        assert saver.is_full_member and saver.membership_number.startswith("EMDI/COOP/")
        assert saver.date_joined == datetime.date.today()
        assert SavingsAccount.objects.filter(member=saver, product__code="REGULAR").exists()
        assert SavingsAccount.objects.filter(pk=christmas.pk, member=saver).exists()
        log = AuditLog.objects.get(action="member.converted_to_member")
        assert log.changes["membership_number"][0] == "EMDI/XMAS/0001"

        assert code(as_user(secretary_admin).post(f"{MEMBERS}{saver.pk}/convert-to-member/", {}, format="json")) == "already_member"
        assert as_user(secretary_admin).post(f"{MEMBERS}{saver.pk}/send-activation/").status_code == 202

    def test_conversion_needs_registration_rights(self, as_user, saver):
        assert as_user(make_officer("Treasurer")).post(f"{MEMBERS}{saver.pk}/convert-to-member/", {}, format="json").status_code == 403


def test_settings_default_saver_format():
    assert CooperativeSettings.load().saver_number_format == "EMDI/XMAS/{seq:04d}"
