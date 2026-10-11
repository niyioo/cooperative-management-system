"""Guarantors (BR-28): chosen by membership number, asked in the portal and by e-mail, and must accept before approval."""
from decimal import Decimal

import pytest
from django.core import mail

from apps.accounts.models import placeholder_email
from apps.audit.models import AuditLog
from apps.loans import services
from apps.loans.models import LoanGuarantor
from apps.members.models import Member
from apps.notifications.models import Notification
from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db
ME = "/api/v1/me/"
D = Decimal


@pytest.fixture
def draft(borrower, product):
    return services.create_application(borrower.user, member=borrower, product=product,
                                       amount_requested=D("100000"), term_months=10, purpose="School fees")


@pytest.fixture
def friend(db):
    return MemberFactory(user=UserFactory(email="friend@example.com", first_name="Femi"), last_name="Friend")


def code(response):
    return response.data["error"]["code"]


class TestChoosingGuarantors:
    def test_lookup_confirms_the_name_by_membership_number(self, as_user, borrower, friend):
        client = as_user(borrower.user)
        found = client.get(f"{ME}guarantor-lookup/", {"membership_number": f"  {friend.membership_number.lower()} "})
        assert found.status_code == 200
        assert found.data == {"membership_number": friend.membership_number, "full_name": friend.full_name}

    @pytest.mark.parametrize("who,expected", [("nobody", "guarantor_not_found"), ("self", "guarantor_is_applicant"), ("suspended", "guarantor_not_active")])
    def test_lookup_refuses_unsuitable_guarantors(self, as_user, borrower, who, expected):
        number = {"nobody": "EMDI/NOPE/9999", "self": borrower.membership_number,
                  "suspended": MemberFactory(status=Member.Status.SUSPENDED).membership_number}[who]
        response = as_user(borrower.user).get(f"{ME}guarantor-lookup/", {"membership_number": number})
        assert response.status_code == 400 and code(response) == expected

    def test_lookup_needs_a_member(self, as_user):
        assert as_user(UserFactory(is_staff_officer=True)).get(f"{ME}guarantor-lookup/", {"membership_number": "X"}).status_code == 403

    def test_add_and_remove_while_editable(self, as_user, borrower, draft, friend):
        client = as_user(borrower.user)
        url = f"{ME}loan-applications/{draft.pk}/guarantors/"
        added = client.post(url, {"membership_number": friend.membership_number})
        assert added.status_code == 201 and added.data["guarantors"][0]["status"] == "PENDING"
        assert code(client.post(url, {"membership_number": friend.membership_number})) == "duplicate_guarantor"
        guarantee_id = added.data["guarantors"][0]["id"]
        assert client.delete(f"{url}{guarantee_id}/").data["guarantors"] == []
        assert AuditLog.objects.filter(action="loan.guarantor_removed").exists()

    def test_guarantors_are_fixed_once_submitted(self, as_user, borrower, draft, friend):
        services.add_guarantor(borrower.user, draft, friend.membership_number)
        services.submit_application(borrower.user, draft)
        other = MemberFactory()
        response = as_user(borrower.user).post(f"{ME}loan-applications/{draft.pk}/guarantors/", {"membership_number": other.membership_number})
        assert code(response) == "invalid_transition"

    def test_other_members_cannot_touch_the_application(self, as_user, draft, friend):
        intruder = MemberFactory()
        response = as_user(intruder.user).post(f"{ME}loan-applications/{draft.pk}/guarantors/", {"membership_number": friend.membership_number})
        assert response.status_code == 404

    def test_products_always_need_a_guarantor(self, as_user, super_admin, product):
        response = as_user(super_admin).patch(f"/api/v1/admin/loans/products/{product.pk}/", {"guarantors_required": 0})
        assert response.status_code == 400 and "guarantors_required" in response.data["error"]["fields"]


class TestAskingGuarantors:
    def test_submitting_notifies_each_guarantor_in_app_and_by_email(self, borrower, draft, friend, django_capture_on_commit_callbacks):
        second = MemberFactory(user=UserFactory(email="second@example.com"))
        services.add_guarantor(borrower.user, draft, friend.membership_number)
        services.add_guarantor(borrower.user, draft, second.membership_number)
        with django_capture_on_commit_callbacks(execute=True):
            services.submit_application(borrower.user, draft)

        shares = sorted(draft.guarantors.values_list("amount_guaranteed", flat=True))
        assert shares == [D("50000.00"), D("50000.00")]
        note = Notification.objects.get(recipient=friend.user)
        assert note.link == "/member/guarantees" and borrower.full_name in note.title and "₦50,000.00" in note.body
        assert sorted(m.to[0] for m in mail.outbox) == ["friend@example.com", "second@example.com"]
        email = next(m for m in mail.outbox if m.to == ["friend@example.com"])
        assert "Guarantor request" in email.subject and "/member/guarantees" in email.body

    def test_uneven_amounts_are_split_to_the_kobo(self, borrower, product, friend):
        application = services.create_application(borrower.user, member=borrower, product=product,
                                                  amount_requested=D("100000"), term_months=10, purpose="x")
        for member in (friend, MemberFactory(), MemberFactory()):
            services.add_guarantor(borrower.user, application, member.membership_number)
        services.submit_application(borrower.user, application)
        shares = list(application.guarantors.order_by("created_at").values_list("amount_guaranteed", flat=True))
        assert shares == [D("33333.34"), D("33333.33"), D("33333.33")] and sum(shares) == D("100000")

    def test_members_without_an_email_are_notified_in_the_portal_only(self, borrower, draft, django_capture_on_commit_callbacks):
        offline = MemberFactory()
        offline.user.email = placeholder_email(offline.membership_number)
        offline.user.save()
        services.add_guarantor(borrower.user, draft, offline.membership_number)
        with django_capture_on_commit_callbacks(execute=True):
            services.submit_application(borrower.user, draft)
        assert Notification.objects.filter(recipient=offline.user).exists()
        assert mail.outbox == []


class TestResponding:
    @pytest.fixture
    def submitted(self, borrower, draft, friend):
        services.add_guarantor(borrower.user, draft, friend.membership_number)
        return services.submit_application(borrower.user, draft)

    def test_the_guarantor_sees_and_accepts_the_request(self, as_user, borrower, friend, submitted, django_capture_on_commit_callbacks):
        client = as_user(friend.user)
        listed = client.get(f"{ME}guarantee-requests/", {"awaiting": "true"}).data["results"]
        assert len(listed) == 1 and listed[0]["can_respond"] is True
        assert listed[0]["applicant"]["full_name"] == borrower.full_name and listed[0]["amount_guaranteed"] == "100000.00"
        with django_capture_on_commit_callbacks(execute=True):
            accepted = client.post(f"{ME}guarantee-requests/{listed[0]['id']}/accept/")
        assert accepted.data["status"] == "ACCEPTED" and accepted.data["can_respond"] is False
        assert client.get(f"{ME}guarantee-requests/", {"awaiting": "true"}).data["count"] == 0
        assert code(client.post(f"{ME}guarantee-requests/{listed[0]['id']}/accept/")) == "already_answered"
        note = Notification.objects.filter(recipient=borrower.user).latest("created_at")
        assert "accepted" in note.title and "committee can now decide" in note.body
        assert [m.to for m in mail.outbox] == [[borrower.user.email]]

    def test_declining_returns_the_application_to_the_applicant(self, as_user, borrower, friend, submitted, django_capture_on_commit_callbacks):
        guarantee = submitted.guarantors.get()
        with django_capture_on_commit_callbacks(execute=True):
            declined = as_user(friend.user).post(f"{ME}guarantee-requests/{guarantee.pk}/decline/", {"reason": "Already guaranteeing two loans"})
        assert declined.data["status"] == "DECLINED"
        submitted.refresh_from_db()
        assert submitted.status == "RETURNED"
        assert "declined to stand as your guarantor (Already guaranteeing two loans)" in submitted.info_request_message
        assert mail.outbox[0].to == [borrower.user.email] and "declined" in mail.outbox[0].subject

        # The applicant chooses someone else and resubmits; the declined guarantor no longer counts.
        replacement = MemberFactory()
        services.add_guarantor(borrower.user, submitted, replacement.membership_number)
        services.submit_application(borrower.user, submitted)
        statuses = dict(submitted.guarantors.values_list("guarantor__membership_number", "status"))
        assert statuses == {friend.membership_number: "DECLINED", replacement.membership_number: "PENDING"}
        assert submitted.guarantors.get(guarantor=replacement).amount_guaranteed == D("100000.00")

    def test_only_the_guarantor_can_answer(self, as_user, borrower, submitted):
        guarantee = submitted.guarantors.get()
        assert as_user(borrower.user).post(f"{ME}guarantee-requests/{guarantee.pk}/accept/").status_code == 404
        assert as_user(MemberFactory().user).post(f"{ME}guarantee-requests/{guarantee.pk}/accept/").status_code == 404

    def test_answers_are_closed_once_the_application_is_decided(self, as_user, friend, submitted, loan_officer, chairman):
        services.start_review(loan_officer, submitted)
        services.reject_application(chairman, submitted, reason="Insufficient savings")
        guarantee = submitted.guarantors.get()
        response = as_user(friend.user).post(f"{ME}guarantee-requests/{guarantee.pk}/accept/")
        assert code(response) == "not_awaiting_guarantors"
        listed = as_user(friend.user).get(f"{ME}guarantee-requests/").data["results"]
        assert listed[0]["can_respond"] is False and listed[0]["application_status"] == "REJECTED"

    def test_changing_the_amount_asks_accepted_guarantors_again(self, borrower, friend, submitted, loan_officer):
        guarantee = submitted.guarantors.get()
        services.respond_to_guarantee(friend.user, guarantee, accept=True)
        services.start_review(loan_officer, submitted)
        services.return_application(loan_officer, submitted, message="Reduce the amount")
        services.update_application(borrower.user, submitted, amount_requested=D("80000"))
        services.submit_application(borrower.user, submitted)
        guarantee.refresh_from_db()
        assert guarantee.status == "PENDING" and guarantee.amount_guaranteed == D("80000.00")
        assert Notification.objects.filter(recipient=friend.user, title__startswith="Guarantor request").count() == 2


def test_paper_applications_name_guarantors_by_membership_number(as_user, loan_officer, borrower, product, friend, django_capture_on_commit_callbacks):
    payload = {"member": str(borrower.pk), "product": str(product.pk), "amount_requested": "60000", "term_months": 6,
               "purpose": "Rent", "guarantors": [friend.membership_number]}
    with django_capture_on_commit_callbacks(execute=True):
        response = as_user(loan_officer).post("/api/v1/admin/loans/applications/", payload, format="json")
    assert response.status_code == 201
    assert response.data["guarantors"][0]["guarantor"]["membership_number"] == friend.membership_number
    assert mail.outbox[0].to == ["friend@example.com"]
    missing = as_user(loan_officer).post("/api/v1/admin/loans/applications/", {**payload, "guarantors": []}, format="json")
    assert missing.status_code == 400
    assert LoanGuarantor.objects.count() == 1
