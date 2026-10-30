from apps.core.testing import APITestBase, money
from apps.finance.models import LedgerEntry
from apps.loans.models import Loan, LoanProduct


class LoanTests(APITestBase):
    url = "/api/v1/loans/applications/"

    def setUp(self):
        super().setUp()
        self.product = LoanProduct.objects.create(
            name="Emergency", interest_rate="10.00", max_amount="100000.00", max_duration_months=12,
        )

    def apply(self, user=None, amount="50000", months=6, member=None):
        self.as_user(user or self.member)
        return self.client.post(self.url, {
            "member_id": str((member or (user or self.member)).member_profile.pk),
            "loan_product_id": str(self.product.pk),
            "principal_amount": amount, "duration_months": months, "purpose": "School fees",
        }, format="json")

    def approved_and_disbursed(self):
        loan = self.apply().data
        self.as_user(self.officer)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/approve/").status_code, 200)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/disburse/").status_code, 200)
        return Loan.objects.get(pk=loan["id"])

    def test_member_can_apply(self):
        response = self.apply()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(money(response.data["total_payable"]), money(55000))

    def test_member_cannot_apply_in_someone_elses_name(self):
        response = self.apply(member=self.other)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["member"]["id"], str(self.member.member_profile.pk))

    def test_application_must_respect_the_product_limits(self):
        self.assertEqual(self.apply(amount="250000").status_code, 400)
        self.assertEqual(self.apply(months=36).status_code, 400)
        self.assertEqual(self.apply(amount="0").status_code, 400)

    def test_inactive_products_cannot_be_used(self):
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.apply().status_code, 400)

    def test_disbursement_credits_savings_once_and_records_the_expense(self):
        loan = self.approved_and_disbursed()
        self.assertEqual(loan.status, "ACTIVE")
        self.assertEqual(self.balance(self.member), money(50000))
        self.assertTrue(LedgerEntry.objects.filter(type="EXPENSE", amount="50000.00", member=self.member.member_profile).exists())

    def test_disbursing_twice_is_refused(self):
        loan = self.approved_and_disbursed()
        self.as_user(self.officer)
        self.assertEqual(self.client.post(f"{self.url}{loan.pk}/disburse/").status_code, 400)
        self.assertEqual(self.balance(self.member), money(50000))

    def test_members_cannot_change_a_loan_after_applying(self):
        loan = self.apply().data
        self.as_user(self.member)
        self.assertIn(self.client.patch(f"{self.url}{loan['id']}/", {"principal_amount": "99999"}, format="json").status_code, (403, 405))
        self.assertEqual(Loan.objects.get(pk=loan["id"]).principal_amount, money(50000))

    def test_members_cannot_approve_their_own_loan(self):
        loan = self.apply().data
        self.as_user(self.member)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/approve/").status_code, 403)


class RepaymentTests(LoanTests):
    rep_url = "/api/v1/loans/repayments/"

    def repay(self, loan, amount, by=None):
        self.as_user(by or self.accountant)
        return self.client.post(self.rep_url, {"loan": str(loan.pk), "amount_paid": str(amount)}, format="json")

    def test_members_cannot_record_their_own_repayments(self):
        loan = self.approved_and_disbursed()
        self.assertEqual(self.repay(loan, "55000", by=self.member).status_code, 403)
        loan.refresh_from_db()
        self.assertEqual(loan.balance_remaining, money(55000))

    def test_staff_repayment_reduces_the_balance_and_records_income(self):
        loan = self.approved_and_disbursed()
        self.assertEqual(self.repay(loan, "5000").status_code, 201)
        loan.refresh_from_db()
        self.assertEqual(loan.balance_remaining, money(50000))
        self.assertTrue(LedgerEntry.objects.filter(type="INCOME", category="Loan Repayment", amount="5000.00").exists())

    def test_final_repayment_completes_the_loan(self):
        loan = self.approved_and_disbursed()
        self.repay(loan, "55000")
        loan.refresh_from_db()
        self.assertEqual((loan.status, loan.balance_remaining), ("COMPLETED", money(0)))

    def test_overpayment_is_refused(self):
        loan = self.approved_and_disbursed()
        self.assertEqual(self.repay(loan, "60000").status_code, 400)

    def test_repayments_only_on_active_loans(self):
        loan = Loan.objects.get(pk=self.apply().data["id"])
        self.assertEqual(self.repay(loan, "100").status_code, 400)

    def test_repayments_cannot_be_edited_or_deleted(self):
        loan = self.approved_and_disbursed()
        rep = self.repay(loan, "5000").data
        self.as_user(self.admin)
        self.assertIn(self.client.delete(f"{self.rep_url}{rep['id']}/").status_code, (403, 405))
        self.assertIn(self.client.patch(f"{self.rep_url}{rep['id']}/", {"amount_paid": "1"}, format="json").status_code, (403, 405))


class SeparationOfDutiesTests(LoanTests):
    def test_staff_cannot_approve_or_disburse_their_own_loan(self):
        loan = self.apply(user=self.officer).data
        self.as_user(self.officer)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/approve/").status_code, 403)
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/approve/").status_code, 200)
        self.as_user(self.officer)
        self.assertEqual(self.client.post(f"{self.url}{loan['id']}/disburse/").status_code, 403)

    def test_loan_staff_can_apply_on_a_members_behalf(self):
        self.as_user(self.officer)
        response = self.client.post(self.url, {
            "member_id": str(self.member.member_profile.pk), "loan_product_id": str(self.product.pk),
            "principal_amount": "20000", "duration_months": 3,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["member"]["id"], str(self.member.member_profile.pk))

    def test_interest_is_rounded_to_the_kobo(self):
        self.product.interest_rate = "7.25"
        self.product.save()
        response = self.apply(amount="333.33")
        self.assertEqual(money(response.data["interest_amount"]), money("24.17"))
