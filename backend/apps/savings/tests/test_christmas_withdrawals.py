"""BR-40: members and Christmas savers may withdraw from Christmas Savings any time while the cycle is open."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.common.exceptions import DomainError
from apps.ledger.models import Transaction
from apps.members.models import Member
from apps.savings import services
from apps.savings.models import SavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db
D = Decimal


def saved(member, cycle, amount):
    account, _ = SavingsAccount.objects.get_or_create(member=member, product=cycle.product, cycle=cycle)
    Transaction.objects.create(member=member, txn_type="SAVINGS_CONTRIBUTION", entry_side="CREDIT", amount=D(amount),
                               savings_account=account, period=cycle.start_date, status="POSTED", posted_at=timezone.now())
    return account


@pytest.mark.parametrize("membership_type", [Member.Type.MEMBER, Member.Type.CHRISTMAS_SAVER])
def test_anyone_saving_can_withdraw_while_the_cycle_is_open(treasurer, open_cycle, membership_type):
    saver = MemberFactory(membership_type=membership_type,
                          membership_number="XMAS/77" if membership_type == Member.Type.CHRISTMAS_SAVER else "")
    account = saved(saver, open_cycle, "40000")
    entry = services.post_withdrawal(treasurer, account=account, amount=D("15000"), reason="School fees")
    assert entry.txn_type == "SAVINGS_WITHDRAWAL" and entry.amount == D("15000.00")
    with pytest.raises(DomainError):
        services.post_withdrawal(treasurer, account=account, amount=D("30000"), reason="More than is left")


def test_no_withdrawals_once_the_cycle_has_closed(treasurer, super_admin, open_cycle):
    account = saved(MemberFactory(), open_cycle, "40000")
    services.close_cycle(super_admin, open_cycle)
    account.refresh_from_db()
    with pytest.raises(DomainError) as error:
        services.post_withdrawal(treasurer, account=account, amount=D("1000"), reason="Too late")
    assert error.value.code in ("cycle_not_open", "account_not_active")
