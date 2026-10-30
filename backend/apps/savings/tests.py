from apps.core.testing import APITestBase, money
from apps.savings.models import SavingsTransaction


class SavingsTests(APITestBase):
    url = "/api/v1/savings/transactions/"

    def test_staff_deposit_is_counted_once(self):
        self.deposit(self.member, "10000")
        self.assertEqual(self.balance(self.member), money(10000))

    def test_member_request_is_counted_once_when_approved(self):
        self.as_user(self.member)
        txn = self.client.post(self.url, {"transaction_type": "DEPOSIT", "amount": "2500"}, format="json").data
        self.assertEqual(txn["status"], "PENDING")
        self.assertEqual(self.balance(self.member), money(0))
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{txn['id']}/approve/").status_code, 200)
        self.assertEqual(self.balance(self.member), money(2500))

    def test_staff_cannot_overdraw_an_account(self):
        self.deposit(self.member, "1000")
        self.as_user(self.accountant)
        response = self.client.post(self.url, {
            "account": str(self.savings(self.member).pk), "transaction_type": "WITHDRAWAL", "amount": "5000",
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balance(self.member), money(1000))

    def test_failed_withdrawal_approval_leaves_it_pending(self):
        self.as_user(self.member)
        txn = self.client.post(self.url, {"transaction_type": "WITHDRAWAL", "amount": "500"}, format="json").data
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{txn['id']}/approve/").status_code, 400)
        self.assertEqual(SavingsTransaction.objects.get(pk=txn["id"]).status, "PENDING")
        self.assertEqual(self.balance(self.member), money(0))

    def test_rejected_transactions_cannot_be_approved(self):
        self.as_user(self.member)
        txn = self.client.post(self.url, {"transaction_type": "DEPOSIT", "amount": "100"}, format="json").data
        self.as_user(self.manager)
        self.assertEqual(self.client.post(f"{self.url}{txn['id']}/reject/", {"reason": "No receipt seen"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{self.url}{txn['id']}/approve/").status_code, 400)
        self.assertEqual(self.balance(self.member), money(0))

    def test_transactions_cannot_be_edited_or_deleted(self):
        txn = self.deposit(self.member, "1000")
        for user in (self.member, self.admin):
            self.as_user(user)
            self.assertIn(self.client.patch(f"{self.url}{txn['id']}/", {"amount": "9999"}, format="json").status_code, (403, 405))
            self.assertIn(self.client.delete(f"{self.url}{txn['id']}/").status_code, (403, 405))
        self.assertEqual(self.balance(self.member), money(1000))

    def test_members_only_see_and_use_their_own_account(self):
        self.deposit(self.other, "700")
        self.as_user(self.member)
        response = self.client.post(self.url, {
            "account": str(self.savings(self.other).pk), "transaction_type": "WITHDRAWAL", "amount": "700",
        }, format="json")
        self.assertEqual(str(response.data["account"]), str(self.savings(self.member).pk))
        ids = [row["id"] for row in self.client.get("/api/v1/savings/accounts/").data["results"]]
        self.assertEqual(ids, [str(self.savings(self.member).pk)])

    def test_members_cannot_credit_themselves_interest_or_dividends(self):
        self.as_user(self.member)
        response = self.client.post(self.url, {"transaction_type": "DIVIDEND", "amount": "1000000"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_amounts_must_be_positive(self):
        self.as_user(self.accountant)
        response = self.client.post(self.url, {
            "account": str(self.savings(self.member).pk), "transaction_type": "DEPOSIT", "amount": "-50",
        }, format="json")
        self.assertEqual(response.status_code, 400)
