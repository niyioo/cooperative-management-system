"""Shared fixtures for the API test suite."""
import itertools
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.members.models import Member
from apps.savings.models import SavingsAccount

PASSWORD = "Str0ng-Pass!word"
_counter = itertools.count(1)


def make_user(role=CustomUser.Role.MEMBER, **extra):
    n = next(_counter)
    user = CustomUser.objects.create_user(
        email=f"{role.lower()}{n}@example.com", password=PASSWORD, role=role, **extra
    )
    # Every user gets a member profile and savings account automatically.
    Member.objects.filter(user=user).update(
        first_name=f"First{n}", last_name=f"Last{n}", status=Member.Status.ACTIVE,
    )
    user.refresh_from_db()
    return user


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


class APITestBase(TestCase):
    """One user per role and an unauthenticated client."""

    def setUp(self):
        cache.clear()
        R = CustomUser.Role
        self.admin = make_user(R.SUPER_ADMIN)
        self.manager = make_user(R.MANAGER)
        self.accountant = make_user(R.ACCOUNTANT)
        self.officer = make_user(R.LOAN_OFFICER)
        self.member = make_user(R.MEMBER)
        self.other = make_user(R.MEMBER)
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def savings(self, user) -> SavingsAccount:
        return SavingsAccount.objects.get(member__user=user)

    def balance(self, user) -> Decimal:
        return self.savings(user).balance

    def deposit(self, user, amount, by=None):
        """Staff-recorded deposit into `user`'s savings."""
        self.as_user(by or self.accountant)
        response = self.client.post("/api/v1/savings/transactions/", {
            "account": str(self.savings(user).pk), "transaction_type": "DEPOSIT", "amount": str(amount),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data
