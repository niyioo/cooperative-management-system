import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.closures import services as closures
from apps.configuration.models import Department
from apps.loans import services as loans
from apps.loans.models import LoanProduct
from apps.members.models import MemberStatus
from apps.notifications.models import Announcement, Broadcast, Notification
from tests.factories import MemberFactory, add_guarantors, make_officer

pytestmark = pytest.mark.django_db
MESSAGES = "/api/v1/admin/messages/"
ANNOUNCEMENTS = "/api/v1/admin/announcements/"
D = Decimal


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


class TestWorkflowNotifications:
    def test_loan_decisions_notify_the_member(self, chairman, this_year):
        member = MemberFactory(date_joined=datetime.date(this_year - 3, 1, 1))
        product = LoanProduct.objects.create(name="Emergency", code="EMG", interest_rate=D("5"), min_amount=D("1000"),
                                             max_amount=D("100000"), min_term_months=1, max_term_months=6)
        officer = make_officer("Loan Officer")
        application = loans.create_application(officer, member=member, product=product, amount_requested=D("5000"), term_months=3, purpose="x")
        add_guarantors(officer, application)
        loans.submit_application(officer, application)
        loans.return_application(officer, application, message="Attach your payslip.")
        note = Notification.objects.get(recipient=member.user)
        assert note.category == "LOAN" and "payslip" in note.body
        assert note.link == f"/member/loans/applications/{application.pk}"

    def test_closure_steps_notify_the_member(self, regular, secretary, chairman):
        member = MemberFactory()
        request = closures.submit_request(member, reason_category="RETIREMENT", reason="Retiring", confirmed=True)
        closures.start_review(secretary, request)
        closures.reject_request(chairman, request, reason="Outstanding guarantee")
        titles = list(Notification.objects.filter(recipient=member.user).order_by("created_at").values_list("title", flat=True))
        assert titles == [f"Closure request {request.reference} is under review", f"Closure request {request.reference} not approved"]


class TestBroadcasts:
    def test_send_to_all_active_members(self, as_user, secretary):
        active = [MemberFactory(status=MemberStatus.ACTIVE) for _ in range(3)]
        MemberFactory(status=MemberStatus.SUSPENDED)
        response = as_user(secretary).post(MESSAGES, {"title": "AGM", "body": "The AGM holds on 12 December.", "audience": "ALL_ACTIVE"})
        assert response.status_code == 201 and response.data["recipient_count"] == 3
        assert Notification.objects.filter(category="MESSAGE", broadcast_id=response.data["id"]).count() == 3
        assert set(Notification.objects.values_list("recipient", flat=True)) == {m.user_id for m in active}
        assert AuditLog.objects.filter(action="notification.broadcast_sent", metadata__recipients=3).exists()

    def test_department_and_selected_audiences(self, as_user, secretary):
        dept = Department.objects.create(name="Ceramics", code="CER")
        in_dept = MemberFactory(department=dept)
        MemberFactory()
        data = as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "DEPARTMENT", "department": dept.pk}).data
        assert data["recipient_count"] == 1 and data["department_name"] == "Ceramics"
        chosen = MemberFactory(status=MemberStatus.SUSPENDED)
        response = as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "SELECTED", "members": [chosen.pk, in_dept.pk]}, format="json")
        assert response.data["recipient_count"] == 2

    def test_validation_and_read_counts(self, as_user, secretary):
        assert as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "DEPARTMENT"}).status_code == 400
        member = MemberFactory()
        for link in ("https://evil.example", "//evil.example", "/member/..\\evil.example", "/member/x?next=//evil"):
            assert as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "ALL_ACTIVE", "link": link}).status_code == 400, link
        assert as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "ALL_ACTIVE", "link": "/member/loans/apply"}).status_code == 201
        sent = as_user(secretary).post(MESSAGES, {"title": "x", "body": "y", "audience": "ALL_ACTIVE"}).data
        Notification.objects.filter(recipient=member.user).update(read_at=timezone.now())
        listed = as_user(secretary).get(MESSAGES).data["results"][0]
        assert listed["id"] == sent["id"] and listed["read_count"] == 1

    def test_requires_send_permission(self, as_user, treasurer):
        assert as_user(treasurer).post(MESSAGES, {"title": "x", "body": "y", "audience": "ALL_ACTIVE"}).status_code == 403
        assert Broadcast.objects.count() == 0


class TestAnnouncements:
    def test_create_list_and_end(self, as_user, secretary, member):
        response = as_user(secretary).post(ANNOUNCEMENTS, {"title": "Office closed", "body": "Closed on Friday.", "audience": "ALL_MEMBERS"})
        assert response.status_code == 201 and response.data["state"] == "LIVE"
        assert as_user(member.user).get("/api/v1/me/announcements/").data["count"] == 1
        ended = as_user(secretary).post(f"{ANNOUNCEMENTS}{response.data['id']}/end/").data
        assert ended["state"] == "ENDED"
        assert as_user(member.user).get("/api/v1/me/announcements/").data["count"] == 0
        assert as_user(secretary).get(ANNOUNCEMENTS, {"state": "ENDED"}).data["count"] == 1
        assert AuditLog.objects.filter(action="announcement.ended").exists()

    def test_scheduled_and_validation(self, as_user, secretary):
        later = timezone.now() + datetime.timedelta(days=2)
        data = as_user(secretary).post(ANNOUNCEMENTS, {"title": "AGM", "body": "Soon", "publish_at": later.isoformat()}).data
        assert data["state"] == "SCHEDULED"
        bad = as_user(secretary).post(ANNOUNCEMENTS, {"title": "AGM", "body": "Soon", "publish_at": later.isoformat(),
                                                       "expires_at": timezone.now().isoformat()})
        assert bad.status_code == 400 and "expires_at" in bad.data["error"]["fields"]
        # Ending a scheduled announcement keeps the dates consistent.
        ended = as_user(secretary).post(f"{ANNOUNCEMENTS}{data['id']}/end/").data
        assert ended["state"] == "ENDED"

    def test_officer_announcements_reach_the_dashboard(self, as_user, secretary, treasurer):
        Announcement.objects.create(title="Audit next week", body="Prepare files.", audience="OFFICERS",
                                    publish_at=timezone.now(), created_by=secretary)
        Announcement.objects.create(title="Members only", body="x", audience="ALL_MEMBERS", publish_at=timezone.now(), created_by=secretary)
        titles = [a["title"] for a in as_user(treasurer).get("/api/v1/admin/dashboard/").data["announcements"]]
        assert titles == ["Audit next week"]

    def test_requires_manage_permission(self, as_user, treasurer):
        assert as_user(treasurer).get(ANNOUNCEMENTS).status_code == 403
