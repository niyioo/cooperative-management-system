from io import StringIO

from django.core.management import call_command

from apps.contributions.models import Contribution
from apps.core.models import SystemSetting
from apps.core.testing import APITestBase, money
from apps.finance.models import LedgerEntry
from apps.shares.models import ShareAccount
from apps.savings.models import SavingsAccount


class LedgerTests(APITestBase):
    url = "/api/v1/finance/ledger/"

    def test_ledger_entries_cannot_be_edited_or_deleted(self):
        self.as_user(self.manager)
        entry = self.client.post(self.url, {
            "type": "EXPENSE", "category": "Office rent", "amount": "50000", "date": "2026-10-01", "description": "October rent",
        }, format="json").data
        self.assertIn(self.client.patch(f"{self.url}{entry['id']}/", {"amount": "1"}, format="json").status_code, (403, 405))
        self.assertIn(self.client.delete(f"{self.url}{entry['id']}/").status_code, (403, 405))
        self.assertEqual(LedgerEntry.objects.get(pk=entry["id"]).amount, money(50000))

    def test_members_cannot_read_the_ledger(self):
        self.as_user(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class ContributionTests(APITestBase):
    url = "/api/v1/contributions/"

    def assess(self, user=None):
        self.as_user(user or self.accountant)
        return self.client.post(self.url, {
            "member_id": str(self.member.member_profile.pk), "type": "FINE", "amount": "2000", "due_date": "2026-11-30",
        }, format="json")

    def test_members_cannot_assess_or_delete_dues(self):
        self.assertEqual(self.assess(self.member).status_code, 403)
        fine = self.assess().data
        self.as_user(self.member)
        self.assertIn(self.client.delete(f"{self.url}{fine['id']}/").status_code, (403, 405))
        self.assertTrue(Contribution.objects.filter(pk=fine["id"]).exists())

    def test_marking_paid_records_income_once(self):
        fine = self.assess().data
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{fine['id']}/mark_paid/").status_code, 200)
        self.assertEqual(self.client.post(f"{self.url}{fine['id']}/mark_paid/").status_code, 400)
        self.assertEqual(LedgerEntry.objects.filter(type="INCOME", amount="2000.00").count(), 1)


class ShareTests(APITestBase):
    url = "/api/v1/shares/transactions/"

    def test_share_price_comes_from_settings_not_the_request(self):
        SystemSetting.objects.create(share_unit_price="500.00")
        self.as_user(self.member)
        response = self.client.post(self.url, {"number_of_shares": 10, "price_per_share": "0.01"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(money(response.data["total_amount"]), money(5000))
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{response.data['id']}/approve/").status_code, 200)
        account = ShareAccount.objects.get(member__user=self.member)
        self.assertEqual((account.total_shares, account.current_value), (10, money(5000)))

    def test_share_transactions_cannot_be_edited(self):
        SystemSetting.objects.create(share_unit_price="500.00")
        self.as_user(self.member)
        txn = self.client.post(self.url, {"number_of_shares": 10}, format="json").data
        self.assertIn(self.client.patch(f"{self.url}{txn['id']}/", {"number_of_shares": 10000}, format="json").status_code, (403, 405))


class ReconciliationTests(APITestBase):
    def test_reconcile_reports_consistent_books_and_catches_tampering(self):
        self.deposit(self.member, "3000")
        out = StringIO()
        call_command("reconcile", stdout=out)
        self.assertIn("consistent", out.getvalue().lower())

        SavingsAccount.objects.filter(member__user=self.member).update(balance="999999.00")
        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command("reconcile", stdout=out)
        self.assertIn("savings", out.getvalue().lower())


class ReversalTests(APITestBase):
    url = "/api/v1/finance/ledger/"

    def test_a_mistake_is_corrected_by_a_reversing_entry_once(self):
        self.as_user(self.accountant)
        entry = self.client.post(self.url, {
            "type": "EXPENSE", "category": "Stationery", "amount": "12000", "description": "Paper (wrong amount)",
        }, format="json").data
        self.assertEqual(self.client.post(f"{self.url}{entry['id']}/reverse/", {"reason": "Entered twice"}, format="json").status_code, 403)
        self.as_user(self.manager)
        response = self.client.post(f"{self.url}{entry['id']}/reverse/", {"reason": "Entered twice"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual((response.data["type"], str(response.data["reverses"])), ("INCOME", entry["id"]))
        self.assertEqual(self.client.post(f"{self.url}{entry['id']}/reverse/", {"reason": "Again"}, format="json").status_code, 400)
        self.assertTrue(self.client.get(f"{self.url}{entry['id']}/").data["reversed"])

    def test_loan_books_reconcile_after_repayments(self):
        from apps.loans.models import LoanProduct
        product = LoanProduct.objects.create(name="Asset", interest_rate="5", max_amount="50000", max_duration_months=6)
        self.as_user(self.member)
        loan = self.client.post("/api/v1/loans/applications/", {
            "loan_product_id": str(product.pk), "principal_amount": "10000", "duration_months": 3,
        }, format="json").data
        self.as_user(self.officer)
        self.client.post(f"/api/v1/loans/applications/{loan['id']}/approve/")
        self.client.post(f"/api/v1/loans/applications/{loan['id']}/disburse/")
        self.as_user(self.accountant)
        self.client.post("/api/v1/loans/repayments/", {"loan": loan["id"], "amount_paid": "4000"}, format="json")
        out = StringIO()
        call_command("reconcile", stdout=out)
        self.assertIn("consistent", out.getvalue().lower())
