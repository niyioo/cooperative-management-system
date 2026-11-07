"""The member portal (/api/v1/me/): a member sees only their own records (BR-16)."""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.closures.models import AccountClosureRequest
from apps.configuration.models import CooperativeSettings
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.ledger.models import Transaction
from apps.loans import services as loans
from apps.loans.models import LoanProduct
from apps.notifications.models import Announcement, Notification
from apps.savings import services as savings
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory, accept_guarantees, add_guarantors, make_officer

from .helpers import pdf_file

pytestmark = pytest.mark.django_db
ME = "/api/v1/me/"
D = Decimal


def code(response):
    return response.data["error"]["code"]


def credit(member, account_field, account, amount, txn_type, **extra):
    return Transaction.objects.create(
        member=member, txn_type=txn_type, entry_side="CREDIT", amount=D(amount),
        status="POSTED", posted_at=timezone.now(), **{account_field: account}, **extra,
    )


@pytest.fixture
def product(db):
    return LoanProduct.objects.create(
        name="Regular Loan", code="REG", interest_rate=D("12"), min_amount=D("10000"), max_amount=D("1000000"),
        max_savings_multiple=D("2"), min_term_months=1, max_term_months=24,
    )


@pytest.fixture
def world(open_cycle, regular, product, this_year, super_admin):
    """Two members, each with savings, a loan and an investment; plus officers."""
    coop = CooperativeSettings.load()
    coop.maker_checker_types = []  # keep set-up short: post everything at once
    coop.save()
    loan_officer, chairman, treasurer = (make_officer(r) for r in ("Loan Officer", "Cooperative Chairman", "Treasurer"))
    shares = InvestmentProduct.objects.create(name="Share Capital", code="SHARES")
    people = {}
    for name in ("Ada", "Bayo"):
        member = MemberFactory(last_name=name, date_joined=datetime.date(this_year - 2, 1, 1))
        reg = SavingsAccount.objects.create(member=member, product=regular)
        credit(member, "savings_account", reg, "100000", "SAVINGS_OPENING_BALANCE")
        xmas = SavingsAccount.objects.get_or_create(member=member, cycle=open_cycle, defaults={"product": open_cycle.product})[0]
        savings.post_contribution(treasurer, account=xmas, amount=D("5000"), period=datetime.date(this_year, 1, 1))
        savings.post_contribution(treasurer, account=xmas, amount=D("5000"), period=datetime.date(this_year, 2, 1))
        investment = InvestmentAccount.objects.create(member=member, product=shares)
        credit(member, "investment_account", investment, "30000", "INVESTMENT_CONTRIBUTION")
        application = loans.create_application(loan_officer, member=member, product=product, amount_requested=D("120000"), term_months=12, purpose="Rent")
        add_guarantors(loan_officer, application)
        loans.submit_application(loan_officer, application)
        accept_guarantees(application)
        loans.start_review(loan_officer, application, notes="Payslip checked; salary covers it")
        loans.approve_application(chairman, application)
        loan = loans.disburse(treasurer, application)
        people[name] = {"member": member, "regular": reg, "xmas": xmas, "investment": investment, "application": application, "loan": loan}
    return people


class TestDashboardAndViews:
    def test_dashboard(self, as_user, world, this_year):
        data = as_user(world["Ada"]["member"].user).get(f"{ME}dashboard/").data
        assert data["member"]["membership_number"] == world["Ada"]["member"].membership_number
        summary = data["summary"]
        assert summary["christmas_savings"] == "10000.00"
        assert summary["other_savings"] == "100000.00"
        assert summary["total_savings"] == "110000.00"
        assert summary["active_loans"] == 1
        assert summary["outstanding_loan"] == "134400.00"
        assert summary["investment"] == "30000.00"
        assert data["upcoming_repayment"]["number"] == 1
        assert len(data["recent_transactions"]) == 5

    def test_christmas_grid(self, as_user, world, this_year):
        data = as_user(world["Ada"]["member"].user).get(f"{ME}savings/christmas/").data
        assert data["year"] == this_year
        assert data["contributions"][f"{this_year}-01"] == "5000.00"
        assert data["contributions"][f"{this_year}-10"] == "0.00"
        assert data["total"] == "10000.00"
        assert data["expected_total"] == "50000.00"

    def test_loan_detail_and_application_hide_internal_notes(self, as_user, world):
        client = as_user(world["Ada"]["member"].user)
        loan = client.get(f"{ME}loans/{world['Ada']['loan'].pk}/").data
        assert loan["outstanding"] == "134400.00" and len(loan["schedule"]) == 12
        application = client.get(f"{ME}loan-applications/{world['Ada']['application'].pk}/").data
        assert "review_notes" not in application and "reviewed_by" not in application
        assert application["status"] == "DISBURSED"

    def test_transactions_filters_and_statements(self, as_user, world):
        client = as_user(world["Ada"]["member"].user)
        all_entries = client.get(f"{ME}transactions/").data
        assert all_entries["count"] == Transaction.objects.filter(member=world["Ada"]["member"]).count()
        christmas_only = client.get(f"{ME}transactions/", {"txn_type": "SAVINGS_CONTRIBUTION"}).data
        assert christmas_only["count"] == 2
        assert christmas_only["results"][0]["type_label"] == "Christmas Savings contribution"

        pdf = client.get(f"{ME}transactions/statement/", {"format": "pdf"})
        assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
        xlsx = client.get(f"{ME}transactions/statement/", {"format": "xlsx", "date_from": "2000-01-01"})
        assert xlsx.status_code == 200 and xlsx.content.startswith(b"PK")

    def test_investments_and_dividends(self, as_user, world):
        client = as_user(world["Ada"]["member"].user)
        assert client.get(f"{ME}investments/").data["total_principal"] == "30000.00"
        assert client.get(f"{ME}dividends/").data == {"total_paid": "0.00", "latest": None, "history": []}


class TestIsolation:
    """Another member's records are simply 'not found' — their existence is never revealed."""

    def test_other_members_records_are_not_found(self, as_user, world):
        ada, bayo = world["Ada"], world["Bayo"]
        client = as_user(ada["member"].user)
        for url in (
            f"{ME}loans/{bayo['loan'].pk}/",
            f"{ME}loans/{bayo['loan'].pk}/repayments/",
            f"{ME}loan-applications/{bayo['application'].pk}/",
            f"{ME}savings/accounts/{bayo['regular'].pk}/transactions/",
            f"{ME}investments/{bayo['investment'].pk}/transactions/",
        ):
            assert client.get(url).status_code == 404, url
        assert client.post(f"{ME}loan-applications/{bayo['application'].pk}/cancel/").status_code == 404

    def test_other_members_records_cannot_be_changed(self, as_user, world):
        from apps.closures import services as closures

        ada, bayo = world["Ada"], world["Bayo"]
        request = closures.submit_request(bayo["member"], reason_category="PERSONAL", reason="Moving away", confirmed=True)
        note = Notification.objects.create(recipient=bayo["member"].user, title="Yours, Bayo", body="…")
        client = as_user(ada["member"].user)
        app = bayo["application"].pk
        attempts = [
            ("get", f"{ME}closure-requests/{request.pk}/"),
            ("post", f"{ME}closure-requests/{request.pk}/withdraw/"),
            ("post", f"{ME}notifications/{note.pk}/read/"),
            ("get", f"{ME}loans/{bayo['loan'].pk}/schedule/"),
            ("patch", f"{ME}loan-applications/{app}/"),
            ("post", f"{ME}loan-applications/{app}/submit/"),
            ("post", f"{ME}loan-applications/{app}/documents/"),
        ]
        for method, url in attempts:
            assert getattr(client, method)(url, {}, format="json").status_code == 404, f"{method} {url}"
        request.refresh_from_db()
        note.refresh_from_db()
        assert request.status == "SUBMITTED" and note.read_at is None
        assert client.get(f"{ME}closure-requests/").data["count"] == 0

    def test_lists_contain_only_own_records(self, as_user, world):
        client = as_user(world["Ada"]["member"].user)
        member_ids = {t["account"]["id"] for t in client.get(f"{ME}transactions/").data["results"] if t["account"]}
        own = {str(world["Ada"][k].pk) for k in ("regular", "xmas", "investment", "loan")}
        assert member_ids <= own
        assert [l["id"] for l in client.get(f"{ME}loans/").data["results"]] == [str(world["Ada"]["loan"].pk)]

    def test_officers_without_a_member_profile_cannot_use_the_member_portal(self, as_user, world):
        assert as_user(make_officer("Treasurer")).get(f"{ME}dashboard/").status_code == 403

    def test_forced_password_change_blocks_the_portal(self, as_user, world):
        user = world["Ada"]["member"].user
        user.must_change_password = True
        user.save()
        assert code(as_user(user).get(f"{ME}dashboard/")) == "password_change_required"


class TestLoanApplication:
    def test_apply_edit_attach_submit_and_cancel(self, as_user, world, product):
        ada = world["Ada"]["member"]
        client = as_user(ada.user)
        products = client.get(f"{ME}loan-products/").data
        assert products[0]["eligibility"]["checks"]  # personal eligibility is shown before applying

        product.max_active_loans = 2
        product.save()
        quote = client.get(f"{ME}loan-products/{product.pk}/quote/", {"amount": "60000", "term_months": 6}).data
        assert quote["total_interest"] == "3600.00" and quote["eligibility"]["eligible"] is True

        draft = client.post(f"{ME}loan-applications/", {"product": str(product.pk), "amount_requested": "50000", "term_months": 6, "purpose": "Equipment"}, format="json").data
        assert draft["status"] == "DRAFT" and draft["can_edit"] is True
        updated = client.patch(f"{ME}loan-applications/{draft['id']}/", {"amount_requested": "60000"}, format="json").data
        assert updated["amount_requested"] == "60000.00"
        upload = client.post(f"{ME}loan-applications/{draft['id']}/documents/", {"title": "Payslip", "file": pdf_file()}, format="multipart")
        assert upload.status_code == 201
        blocked = client.post(f"{ME}loan-applications/{draft['id']}/submit/")
        assert blocked.data["error"]["code"] == "guarantors_required"
        bayo = world["Bayo"]["member"]
        with_guarantor = client.post(f"{ME}loan-applications/{draft['id']}/guarantors/", {"membership_number": bayo.membership_number.lower()})
        assert with_guarantor.status_code == 201
        assert with_guarantor.data["guarantors"][0]["full_name"] == bayo.full_name
        submitted = client.post(f"{ME}loan-applications/{draft['id']}/submit/").data
        assert submitted["status"] == "SUBMITTED" and submitted["can_edit"] is False
        assert submitted["guarantors"][0]["amount_guaranteed"] == "60000.00"
        assert client.post(f"{ME}loan-applications/{draft['id']}/documents/", {"title": "x", "file": pdf_file()}, format="multipart").status_code == 400
        assert client.post(f"{ME}loan-applications/{draft['id']}/cancel/", {"reason": "Changed my mind"}).data["status"] == "CANCELLED"


class TestProfileClosureNotifications:
    def test_member_updates_contact_details_only(self, as_user, world):
        ada = world["Ada"]["member"]
        response = as_user(ada.user).patch(f"{ME}profile/", {"phone": "0805 555 0000", "email": "evil@example.com", "last_name": "X"}, format="json")
        assert response.status_code == 200
        ada.refresh_from_db()
        assert ada.phone == "08055550000" and ada.last_name == "Ada" and ada.user.email != "evil@example.com"
        assert code(as_user(ada.user).patch(f"{ME}profile/", {"phone": "abc"}, format="json")) == "validation_error"

    def test_closure_request_lifecycle(self, as_user, world):
        client = as_user(world["Ada"]["member"].user)
        unconfirmed = client.post(f"{ME}closure-requests/", {"reason_category": "RETIREMENT", "reason": "Retiring in December", "confirmed": False})
        assert code(unconfirmed) == "confirmation_required"
        created = client.post(f"{ME}closure-requests/", {"reason_category": "RETIREMENT", "reason": "Retiring in December", "confirmed": True}).data
        assert created["status"] == "SUBMITTED" and created["can_withdraw"] is True
        assert code(client.post(f"{ME}closure-requests/", {"reason_category": "OTHER", "reason": "x", "confirmed": True})) == "request_open"
        assert client.post(f"{ME}closure-requests/{created['id']}/withdraw/").data["status"] == "WITHDRAWN"

        again = client.post(f"{ME}closure-requests/", {"reason_category": "RETIREMENT", "reason": "Retiring", "confirmed": True}).data
        AccountClosureRequest.objects.filter(pk=again["id"]).update(status="UNDER_REVIEW")
        assert code(client.post(f"{ME}closure-requests/{again['id']}/withdraw/")) == "invalid_transition"
        # Submitting changes nothing about the membership itself (BR-12).
        assert client.get(f"{ME}dashboard/").data["member"]["status"] == "ACTIVE"

    def test_notifications_and_announcements(self, as_user, world, super_admin):
        ada, bayo = world["Ada"]["member"], world["Bayo"]["member"]
        Notification.objects.all().delete()  # drop the ones the world's loan workflow created; this test is about scoping
        Notification.objects.create(recipient=ada.user, title="Loan disbursed", body="…")
        Notification.objects.create(recipient=bayo.user, title="Not yours", body="…")
        now = timezone.now()
        Announcement.objects.create(title="AGM on 12 December", body="…", publish_at=now, created_by=super_admin)
        Announcement.objects.create(title="Officers only", body="…", audience="OFFICERS", publish_at=now, created_by=super_admin)
        Announcement.objects.create(title="Expired", body="…", publish_at=now - datetime.timedelta(days=9),
                                    expires_at=now - datetime.timedelta(days=1), created_by=super_admin)

        client = as_user(ada.user)
        notes = client.get(f"{ME}notifications/").data["results"]
        assert [n["title"] for n in notes] == ["Loan disbursed"]
        assert client.get(f"{ME}notifications/unread-count/").data == {"unread": 1}
        client.post(f"{ME}notifications/{notes[0]['id']}/read/")
        assert client.get(f"{ME}notifications/unread-count/").data == {"unread": 0}
        assert [a["title"] for a in client.get(f"{ME}announcements/").data["results"]] == ["AGM on 12 December"]
