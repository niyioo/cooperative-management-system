import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from apps.common.exceptions import DomainError
from apps.loans import services
from apps.loans.models import LoanApplication, LoanGuarantor
from apps.members.models import Member
from tests.factories import MemberFactory, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db

APPS = "/api/v1/admin/loans/applications/"


def code(response):
    return response.data["error"]["code"]


def on_behalf(client, member, product, amount="120000", term=12, accept=True):
    """File a paper application with one guarantor, who accepts unless accept=False."""
    guarantor = MemberFactory()
    response = client.post(
        APPS,
        {"member": str(member.pk), "product": str(product.pk), "amount_requested": amount, "term_months": term,
         "purpose": "Rent", "guarantors": [guarantor.membership_number]},
        format="json",
    )
    if accept and response.status_code == 201:
        services.respond_to_guarantee(guarantor.user, LoanGuarantor.objects.get(application_id=response.data["id"]), accept=True)
    return response


class TestEligibility:
    def test_savings_security_caps_the_loan(self, as_user, loan_officer, borrower, product):
        response = as_user(loan_officer).get(
            "/api/v1/admin/loans/eligibility/",
            {"member": str(borrower.pk), "product": str(product.pk), "amount": "250000", "term_months": 12},
        )
        assert response.data["max_amount"] == "200000.00"  # 2 × ₦100,000 savings
        assert response.data["eligible"] is False
        failed = [c["code"] for c in response.data["checks"] if not c["passed"]]
        assert failed == ["savings_security"]

    def test_christmas_savings_do_not_count_as_security(self):
        from apps.loans.eligibility import eligible_savings
        from apps.savings.models import SavingsProduct

        assert SavingsProduct.objects.get(code="CHRISTMAS").counts_toward_loan_eligibility is False
        assert eligible_savings(MemberFactory()) == 0

    def test_quote(self, as_user, loan_officer, product):
        quote = as_user(loan_officer).get(f"/api/v1/admin/loans/products/{product.pk}/quote/", {"amount": "120000", "term_months": 12}).data
        assert quote["total_interest"] == "14400.00"
        assert quote["monthly_payment"] == "11200.00"
        assert len(quote["instalments"]) == 12


class TestWorkflow:
    def test_paper_application_is_submitted_with_an_eligibility_snapshot(self, as_user, loan_officer, borrower, product):
        response = on_behalf(as_user(loan_officer), borrower, product)
        assert response.status_code == 201, response.data
        assert response.data["status"] == "SUBMITTED"
        assert response.data["eligibility_snapshot"]["eligible"] is True
        assert response.data["quote"]["total_payable"] == "134400.00"

    def test_ineligible_member_cannot_submit(self, as_user, loan_officer, borrower, product):
        Member.objects.filter(pk=borrower.pk).update(status=Member.Status.SUSPENDED)
        response = on_behalf(as_user(loan_officer), borrower, product)
        assert code(response) == "not_eligible"
        assert not LoanApplication.objects.exists()

    def test_new_member_is_too_new(self, as_user, loan_officer, product):
        newcomer = MemberFactory()
        assert code(on_behalf(as_user(loan_officer), newcomer, product)) == "not_eligible"

    def test_review_comes_before_approval(self, as_user, loan_officer, chairman, borrower, product):
        application_id = on_behalf(as_user(loan_officer), borrower, product).data["id"]
        assert code(as_user(chairman).post(f"{APPS}{application_id}/approve/")) == "invalid_transition"
        assert as_user(loan_officer).post(f"{APPS}{application_id}/start-review/").data["status"] == "UNDER_REVIEW"
        approved = as_user(chairman).post(f"{APPS}{application_id}/approve/", {"approved_amount": "100000", "approved_term_months": 10})
        assert approved.data["status"] == "APPROVED"
        assert approved.data["approved_amount"] == "100000.00"
        assert approved.data["quote"]["total_interest"] == "10000.00"  # 12% p.a. over 10 months

    def test_approval_rechecks_eligibility(self, as_user, loan_officer, chairman, borrower, product):
        application_id = on_behalf(as_user(loan_officer), borrower, product).data["id"]
        as_user(loan_officer).post(f"{APPS}{application_id}/start-review/")
        response = as_user(chairman).post(f"{APPS}{application_id}/approve/", {"approved_amount": "300000"})
        assert code(response) == "not_eligible"

    def test_return_edit_and_resubmit(self, as_user, loan_officer, borrower, product):
        client = as_user(loan_officer)
        application_id = on_behalf(client, borrower, product).data["id"]
        client.post(f"{APPS}{application_id}/start-review/")
        returned = client.post(f"{APPS}{application_id}/return/", {"message": "Attach your pay slip."})
        assert returned.data["status"] == "RETURNED"
        assert returned.data["info_request_message"] == "Attach your pay slip."

        application = LoanApplication.objects.get(pk=application_id)
        services.update_application(borrower.user, application, amount_requested=Decimal("90000"))
        services.submit_application(borrower.user, application)
        application.refresh_from_db()
        assert application.status == "SUBMITTED" and application.amount_requested == Decimal("90000")

    def test_reject_needs_a_reason(self, as_user, loan_officer, chairman, borrower, product):
        application_id = on_behalf(as_user(loan_officer), borrower, product).data["id"]
        assert code(as_user(chairman).post(f"{APPS}{application_id}/reject/", {})) == "validation_error"
        rejected = as_user(chairman).post(f"{APPS}{application_id}/reject/", {"reason": "Existing obligations"})
        assert rejected.data["status"] == "REJECTED"
        assert rejected.data["decision_reason"] == "Existing obligations"

    def test_only_one_open_application_per_product(self, as_user, loan_officer, borrower, product):
        on_behalf(as_user(loan_officer), borrower, product)
        assert code(on_behalf(as_user(loan_officer), borrower, product, amount="50000")) == "not_eligible"

    def test_only_the_applicant_cancels(self, loan_officer, borrower, product):
        application = services.create_application(borrower.user, member=borrower, product=product,
                                                  amount_requested=Decimal("50000"), term_months=6, purpose="x")
        with pytest.raises(PermissionDenied):
            services.cancel_application(loan_officer, application)
        assert services.cancel_application(borrower.user, application).status == "CANCELLED"

    def test_officers_cannot_approve_their_own_loans(self, as_user, loan_officer, product):
        officer_member = MemberFactory(user=make_officer("Cooperative Chairman"), date_joined=datetime.date(2020, 1, 1))
        give_savings(officer_member, "100000")
        application_id = on_behalf(as_user(loan_officer), officer_member, product).data["id"]
        as_user(loan_officer).post(f"{APPS}{application_id}/start-review/")
        assert code(as_user(officer_member.user).post(f"{APPS}{application_id}/approve/")) == "self_dealing"

    def test_guarantors_are_enforced_when_required(self, loan_officer, chairman, borrower, product):
        application = services.create_application(loan_officer, member=borrower, product=product,
                                                  amount_requested=Decimal("50000"), term_months=6, purpose="x")
        with pytest.raises(DomainError) as exc:
            services.submit_application(loan_officer, application)
        assert exc.value.code == "guarantors_required"
        guarantor = MemberFactory()
        services.add_guarantor(loan_officer, application, guarantor.membership_number)
        services.submit_application(loan_officer, application)
        services.start_review(loan_officer, application)
        with pytest.raises(DomainError) as exc:
            services.approve_application(chairman, application)  # not accepted yet
        assert exc.value.code == "guarantors_required"
        services.respond_to_guarantee(guarantor.user, application.guarantors.get(), accept=True)
        assert services.approve_application(chairman, application).status == "APPROVED"

