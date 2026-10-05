from decimal import Decimal

from django.utils import timezone

from apps.ledger.models import Transaction
from apps.savings.models import SavingsAccount, SavingsProduct


def give_savings(member, amount):
    """A posted Regular Savings balance (security for loans)."""
    account, _ = SavingsAccount.objects.get_or_create(
        member=member, product=SavingsProduct.objects.get(code="REGULAR"), cycle=None
    )
    Transaction.objects.create(
        member=member, txn_type="SAVINGS_OPENING_BALANCE", entry_side="CREDIT", amount=Decimal(amount),
        savings_account=account, status="POSTED", posted_at=timezone.now(),
    )
    return account
