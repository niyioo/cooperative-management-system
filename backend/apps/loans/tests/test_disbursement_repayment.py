import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import DomainError
from apps.configuration.models import CooperativeSettings
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.loans.models import Loan, RepaymentAllocation
from apps.loans.selectors import loan_schedule
from apps.members.tests.helpers import xlsx_file
from tests.factories import MemberFactory, make_officer

from .helpers import give_savings

pytestmark = pytest.mark.django_db

APPS = "/api/v1/admin/loans/applications/"
LOANS = "/api/v1/admin/loans/"
D = Decimal


def code(response):
    return response.data["error"]["code"]


def disbursement_entry(loan):
    return Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT")


def active_loan(approved, treasurer, chairman, **kwargs):
    """Disburse an approved application and have a second officer approve the disbursement."""
    disbursed_on = kwargs.pop("disbursed_on", None)
    application = approved(**kwargs)
    loan = services.disburse(treasurer, application, disbursed_on=disbursed_on)
    ledger.approve_entry(chairman, disbursement_entry(loan))
    loan.refresh_from_db()
    return loan


class TestDisbursement:
    def test_disbursement_waits_for_a_second_officer(self, as_user, treasurer, chairman, approved):
        application = approved()
        response = as_user(treasurer).post(f"{APPS}{application.pk}/disburse/")
        assert response.status_code == 200, response.data
        assert response.data["status"] == "PENDING_DISBURSEMENT"
        assert response.data["outstanding"] == "0.00"  # nothing is owed until the money actually goes out
        loan = Loan.objects.get(pk=response.data["id"])
        assert loan.installments.count() == 12
        assert not Transaction.objects.filter(loan=loan, txn_type="LOAN_INTEREST_CHARGE").exists()
        assert code(as_user(treasurer).post(f"{APPS}{application.pk}/disburse/")) == "disbursement_pending"

        as_user(chairman).post(f"/api/v1/admin/transactions/{disbursement_entry(loan).pk}/approve/")
        loan.refresh_from_db()
        application.refresh_from_db()
        assert loan.status == Loan.Status.ACTIVE
        assert application.status == "DISBURSED"
        assert services.outstanding(loan) == D("134400.00")  # principal + flat interest

    def test_rejected_disbursement_can_be_retried(self, treasurer, chairman, approved):
        application = approved()
        loan = services.disburse(treasurer, application)
        ledger.reject_entry(chairman, disbursement_entry(loan), reason="Wrong bank account")
        loan.refresh_from_db()
        assert loan.status == Loan.Status.CANCELLED
        retry = services.disburse(treasurer, application)
        assert retry.pk != loan.pk and retry.status == Loan.Status.PENDING_DISBURSEMENT

    def test_without_maker_checker_the_loan_is_active_at_once(self, treasurer, approved):
        coop = CooperativeSettings.load()
        coop.maker_checker_types = [t for t in coop.maker_checker_types if t != "LOAN_DISBURSEMENT"]
        coop.save()
        loan = services.disburse(treasurer, approved())
        assert loan.status == Loan.Status.ACTIVE

    def test_upfront_interest(self, treasurer, chairman, approved, product):
        product.interest_collection = "UPFRONT"
        product.save()
        loan = active_loan(approved, treasurer, chairman)
        assert services.outstanding(loan) == D("120000.00")  # interest already deducted
        assert {r["interest_due"] for r in loan_schedule(loan)} == {D("0.00")}
        assert Transaction.objects.filter(loan=loan, external_reference=services.UPFRONT_INTEREST_REFERENCE).exists()

    def test_terms_are_snapshotted(self, treasurer, chairman, approved, product):
        loan = active_loan(approved, treasurer, chairman)
        product.interest_rate = D("30")
        product.save()
        loan.refresh_from_db()
        assert loan.interest_rate == D("12.0000")


class TestRepayments:
    def test_allocation_goes_interest_first_oldest_first(self, as_user, treasurer, chairman, approved):
        loan = active_loan(approved, treasurer, chairman)
        client = as_user(treasurer)
        assert client.post(f"{LOANS}{loan.pk}/repayments/", {"amount": "11200"}).status_code == 201
        client.post(f"{LOANS}{loan.pk}/repayments/", {"amount": "1500"})

        rows = loan_schedule(loan)
        assert rows[0]["status"] == "PAID"
        assert rows[1]["paid"] == D("1500.00")
        partial = RepaymentAllocation.objects.get(installment__number=2)
        assert partial.interest_amount == D("1200.00") and partial.principal_amount == D("300.00")

        detail = client.get(f"{LOANS}{loan.pk}/").data
        assert detail["outstanding"] == "121700.00"
        assert detail["next_instalment"]["number"] == 2
        repayments = client.get(f"{LOANS}{loan.pk}/repayments/").data["results"]
        assert repayments[0]["principal_component"] == "300.00"  # most recent first

    def test_overpayment_is_refused(self, as_user, treasurer, chairman, approved):
        loan = active_loan(approved, treasurer, chairman)
        response = as_user(treasurer).post(f"{LOANS}{loan.pk}/repayments/", {"amount": "134400.01"})
        assert code(response) == "overpayment"

    def test_full_repayment_completes_the_loan(self, treasurer, chairman, approved):
        loan = active_loan(approved, treasurer, chairman)
        services.record_repayment(treasurer, loan, amount=D("134400"))
        loan.refresh_from_db()
        assert loan.status == Loan.Status.COMPLETED
        assert loan.completed_on == timezone.localdate()
        assert all(r["status"] == "PAID" for r in loan_schedule(loan))

    def test_officer_cannot_record_own_repayment(self, treasurer, chairman, approved):
        officer = make_officer("Treasurer", email="own@example.com")
        member = MemberFactory(user=officer, date_joined=datetime.date(2020, 1, 1))
        give_savings(member, "100000")
        loan = active_loan(approved, treasurer, chairman, member=member)
        with pytest.raises(DomainError) as exc:
            services.record_repayment(officer, loan, amount=D("1000"))
        assert exc.value.code == "self_dealing"


class TestRepaymentBatch:
    def test_payroll_repayments(self, as_user, treasurer, chairman, approved, borrower):
        loan = active_loan(approved, treasurer, chairman)
        other = MemberFactory(date_joined=datetime.date(2020, 1, 1))
        give_savings(other, "100000")
        other_loan = active_loan(approved, treasurer, chairman, member=other, amount="60000", term=6)

        header = ["Membership number", "Amount", "Month"]
        rows = [[borrower.membership_number, 11200, "2026-02"], [other.membership_number, 999999, "2026-02"]]
        accountant = make_officer("Accountant")
        bad = as_user(accountant).post("/api/v1/admin/batches/", {"batch_type": "LOAN_REPAYMENTS", "file": xlsx_file(header, rows)}, format="multipart").data
        assert bad["status"] == "DRAFT"
        assert "still owed" in bad["validation_report"]["errors"][0]["errors"]["amount"][0]

        rows[1][1] = 10600
        batch = as_user(accountant).post("/api/v1/admin/batches/", {"batch_type": "LOAN_REPAYMENTS", "file": xlsx_file(header, rows)}, format="multipart").data
        assert batch["status"] == "VALIDATED", batch["validation_report"]
        as_user(accountant).post(f"/api/v1/admin/batches/{batch['id']}/submit/")
        assert as_user(treasurer).post(f"/api/v1/admin/batches/{batch['id']}/approve/").data["status"] == "POSTED"

        assert loan_schedule(loan)[0]["status"] == "PAID"
        assert loan_schedule(other_loan)[0]["status"] == "PAID"  # ₦60,000 + ₦3,600 over 6 = ₦10,600

    def test_member_with_two_loans_needs_a_reference(self, as_user, treasurer, chairman, approved, borrower, product):
        active_loan(approved, treasurer, chairman)
        product.max_active_loans = 2
        product.save()
        active_loan(approved, treasurer, chairman, amount="20000", term=6)
        batch = as_user(treasurer).post(
            "/api/v1/admin/batches/",
            {"batch_type": "LOAN_REPAYMENTS", "file": xlsx_file(["Membership number", "Amount"], [[borrower.membership_number, 5000]])},
            format="multipart",
        ).data
        assert "2 running loans" in batch["validation_report"]["errors"][0]["errors"]["loan"][0]


class TestOverdueAndDefault:
    def test_overdue_list_and_marking_default(self, as_user, treasurer, chairman, approved):
        four_months_ago = timezone.localdate() - datetime.timedelta(days=125)
        loan = active_loan(approved, treasurer, chairman, disbursed_on=four_months_ago)
        overdue = as_user(treasurer).get(f"{LOANS}overdue/").data["results"]
        assert [o["reference"] for o in overdue] == [loan.reference]
        arrears = overdue[0]["arrears"]
        assert arrears["instalments"] >= 3 and D(arrears["amount"]) == D("11200.00") * arrears["instalments"]

        response = as_user(treasurer).post(f"{LOANS}{loan.pk}/mark-default/", {"reason": "No repayment for four months"})
        assert response.data["status"] == "DEFAULTED"
        # Repayments are still accepted on a defaulted loan.
        assert as_user(treasurer).post(f"{LOANS}{loan.pk}/repayments/", {"amount": "5000"}).status_code == 201

    def test_up_to_date_loan_cannot_be_defaulted(self, as_user, treasurer, chairman, approved):
        loan = active_loan(approved, treasurer, chairman)
        assert code(as_user(treasurer).post(f"{LOANS}{loan.pk}/mark-default/", {"reason": "x"})) == "not_overdue"


def test_loan_list_and_member_summary(as_user, treasurer, chairman, approved, borrower):
    loan = active_loan(approved, treasurer, chairman)
    listing = as_user(treasurer).get(LOANS).data["results"]
    assert listing[0]["reference"] == loan.reference and listing[0]["outstanding"] == "134400.00"
    summary = as_user(treasurer).get(f"/api/v1/admin/members/{borrower.pk}/financial-summary/").data["loans"]
    assert summary["active_count"] == 1 and summary["outstanding"] == "134400.00"


class TestCorrections:
    def test_reversing_a_repayment_reopens_the_loan(self, as_user, treasurer, chairman, approved):
        from apps.ledger import corrections

        loan = active_loan(approved, treasurer, chairman)
        repayment = services.record_repayment(treasurer, loan, amount=D("134400"))
        loan.refresh_from_db()
        assert loan.status == Loan.Status.COMPLETED

        reversal = corrections.reverse_entry(treasurer, repayment, reason="Cheque bounced")
        ledger.approve_entry(chairman, reversal)
        loan.refresh_from_db()
        assert loan.status == Loan.Status.ACTIVE and loan.completed_on is None
        assert services.outstanding(loan) == D("134400.00")
        assert all(r["status"] != "PAID" for r in loan_schedule(loan))  # the reversed allocations no longer count

    def test_disbursements_are_not_reversible_and_loans_are_not_adjustable(self, treasurer, chairman, approved):
        from apps.ledger import corrections

        loan = active_loan(approved, treasurer, chairman)
        with pytest.raises(DomainError) as exc:
            corrections.reverse_entry(treasurer, disbursement_entry(loan), reason="x")
        assert exc.value.code == "not_reversible"
        with pytest.raises(DomainError) as exc:
            corrections.post_adjustment(treasurer, account=loan, entry_side="CREDIT", amount=D("100"), reason="Waiver")
        assert exc.value.code == "adjustment_not_allowed"
