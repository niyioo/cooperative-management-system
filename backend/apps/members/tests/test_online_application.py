"""BR-39: anyone can apply to join online; the Secretary recommends and the Chairman approves (made-up people)."""
import pytest
from django.core import mail

from apps.members.models import Member
from apps.notifications.models import Notification
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db
URL = "/api/v1/public/membership-applications/"


@pytest.fixture
def referees(db):
    return MemberFactory(membership_number="301"), MemberFactory(membership_number="302")


def form(**changes):
    data = {
        "title": "MRS", "first_name": "Ngozi", "middle_name": "Ada", "last_name": "Eze", "gender": "FEMALE",
        "email": "ngozi.eze@example.com", "phone": "08031234567", "residential_address": "12 Oba Adesida Road, Akure",
        "designation": "Scientific Officer", "grade_level": "CR 08", "bank_name": "Union Bank", "bank_account_number": "0123456789",
        "bank_account_name": "Ngozi Eze", "other_cooperatives": "", "other_debts": "",
        "referee_one": "301", "referee_two": "302", "certify": True,
        "next_of_kin": {"full_name": "Obi Eze", "relationship": "Husband", "phone": "08039876543"},
    }
    data.update(changes)
    return data


def test_anyone_can_apply_without_signing_in(api, referees):
    secretary = make_officer("Cooperative Secretary")
    response = api.post(URL, form(), format="json")
    assert response.status_code == 201, response.data
    member = Member.objects.get(membership_number=response.data["reference"])
    assert member.status == "PENDING" and member.applied_online and member.application_date
    assert (member.referee_one.membership_number, member.referee_two.membership_number) == ("301", "302")
    assert member.next_of_kin.get().full_name == "Obi Eze"
    assert not member.user.has_usable_password()  # no portal access until approved
    assert Notification.objects.filter(recipient=secretary, title__contains="Ngozi").exists()


def test_the_form_is_checked(api, referees):
    unticked = api.post(URL, form(certify=False), format="json")
    assert "certify" in unticked.data["error"]["fields"]
    unknown = api.post(URL, form(referee_two="999"), format="json")
    assert "referee_two" in unknown.data["error"]["fields"]
    same = api.post(URL, form(referee_two="301"), format="json")
    assert "referee_two" in same.data["error"]["fields"]
    assert not Member.objects.filter(last_name="Eze").exists()


def test_officer_only_fields_cannot_be_set_by_applicants(api, referees):
    response = api.post(URL, form(is_official=True, monthly_net_pay="900000", membership_number="1"), format="json")
    member = Member.objects.get(membership_number=response.data["reference"])
    assert not member.is_official and member.monthly_net_pay is None and member.membership_number != "1"


def test_bots_filling_the_hidden_field_are_ignored(api, referees):
    response = api.post(URL, form(website="http://spam.example"), format="json")
    assert response.status_code == 201 and not Member.objects.filter(last_name="Eze").exists()


def test_the_secretary_recommends_and_the_chairman_approves(api, as_user, referees, django_capture_on_commit_callbacks):
    secretary, chairman = make_officer("Cooperative Secretary"), make_officer("Cooperative Chairman")
    member = Member.objects.get(membership_number=api.post(URL, form(), format="json").data["reference"])
    base = f"/api/v1/admin/members/{member.pk}/"

    early = as_user(chairman).post(f"{base}activate/")
    assert early.data["error"]["code"] == "not_recommended"
    no_reason = as_user(secretary).post(f"{base}recommend/", {"recommended": False}, format="json")
    assert no_reason.status_code == 400
    recommended = as_user(secretary).post(f"{base}recommend/", {"recommended": True, "note": "Referees confirmed"}, format="json")
    assert recommended.data["recommendation"] == "RECOMMENDED"
    assert as_user(secretary).post(f"{base}activate/").data["error"]["code"] == "maker_checker"

    with django_capture_on_commit_callbacks(execute=True):
        approved = as_user(chairman).post(f"{base}activate/")
    assert approved.data["status"] == "ACTIVE"
    assert len(mail.outbox) == 1 and "ngozi.eze@example.com" in mail.outbox[0].to  # link to set a password


def test_departments_are_listed_for_the_form(api):
    data = api.get("/api/v1/public/departments/").data
    assert "society" in data and isinstance(data["departments"], list)
