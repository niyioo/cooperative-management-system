"""
Database-level guarantees (D1, D8, D11, BR-17): even code that bypasses the
services, or a support engineer at a SQL prompt, cannot rewrite history.
"""
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.ledger.models import Transaction
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def posted(regular):
    member = MemberFactory()
    account = SavingsAccount.objects.create(member=member, product=regular)
    return Transaction.objects.create(member=member, savings_account=account, txn_type="SAVINGS_CONTRIBUTION",
                                      entry_side="CREDIT", amount=Decimal("5000"), status="POSTED", posted_at=timezone.now())


def refused(statement):
    with pytest.raises(DatabaseError), transaction.atomic():
        statement()


class TestLedgerIsAppendOnly:
    def test_posted_entries_cannot_be_edited_or_deleted(self, posted):
        refused(lambda: Transaction.objects.filter(pk=posted.pk).update(amount=Decimal("1")))
        refused(lambda: Transaction.objects.filter(pk=posted.pk).update(status="PENDING"))
        refused(lambda: Transaction.objects.filter(pk=posted.pk).delete())
        posted.refresh_from_db()
        assert posted.amount == Decimal("5000.00") and posted.status == "POSTED"

    def test_new_entries_cannot_start_as_reversed_or_rejected(self, posted):
        for status in ("REVERSED", "REJECTED"):
            refused(lambda s=status: Transaction.objects.create(
                member=posted.member, savings_account=posted.savings_account, txn_type="SAVINGS_CONTRIBUTION",
                entry_side="CREDIT", amount=Decimal("1"), status=s))

    def test_pending_entries_change_only_by_approval(self, posted):
        pending = Transaction.objects.create(member=posted.member, savings_account=posted.savings_account,
                                             txn_type="SAVINGS_CONTRIBUTION", entry_side="CREDIT", amount=Decimal("100"), status="PENDING")
        refused(lambda: Transaction.objects.filter(pk=pending.pk).update(amount=Decimal("999")))
        Transaction.objects.filter(pk=pending.pk).update(status="REJECTED")
        refused(lambda: Transaction.objects.filter(pk=pending.pk).update(status="POSTED"))  # rejected is final


class TestAuditLogIsAppendOnly:
    def test_audit_entries_cannot_be_changed_or_removed(self, super_admin):
        entry = record("test.event", actor=super_admin, metadata={"x": 1})
        refused(lambda: AuditLog.objects.filter(pk=entry.pk).update(action="tampered"))
        refused(lambda: AuditLog.objects.filter(pk=entry.pk).delete())
        assert AuditLog.objects.get(pk=entry.pk).action == "test.event"
