"""
Check that every stored balance matches the transactions behind it.

    python manage.py reconcile          # report; exits 1 if anything disagrees

Read-only: it never changes data. Run it daily (and after restoring a backup);
a non-zero exit can drive an alert. Run it once after upgrading from the old
version: balances recorded before the fix may have been counted twice.
"""
import sys
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum

from apps.loans.models import Loan
from apps.savings.models import SavingsAccount, SavingsTransaction
from apps.shares.models import ShareAccount

ZERO = Decimal('0.00')


def _sum(qs, field):
    return qs.aggregate(total=Sum(field))['total'] or ZERO


def savings_issues():
    Type = SavingsTransaction.TransactionType
    approved = Q(transactions__status=SavingsTransaction.Status.APPROVED)
    credits = Q(transactions__transaction_type__in=[Type.DEPOSIT, Type.DIVIDEND, Type.INTEREST])
    rows = SavingsAccount.objects.select_related('member').annotate(
        credits=Sum('transactions__amount', filter=approved & credits),
        debits=Sum('transactions__amount', filter=approved & Q(transactions__transaction_type=Type.WITHDRAWAL)),
    )
    for account in rows:
        expected = (account.credits or ZERO) - (account.debits or ZERO)
        if account.balance != expected:
            yield (f"Savings {account.account_number} ({account.member.membership_id}): "
                   f"balance ₦{account.balance:,.2f}, transactions say ₦{expected:,.2f}")


def loan_issues():
    for loan in Loan.objects.filter(status__in=[Loan.Status.ACTIVE, Loan.Status.COMPLETED]).select_related('member'):
        expected = loan.total_payable - _sum(loan.repayments.all(), 'amount_paid')
        if loan.balance_remaining != expected:
            yield (f"Loan {loan.loan_id}: balance ₦{loan.balance_remaining:,.2f}, "
                   f"total payable less repayments is ₦{expected:,.2f}")
        if loan.status == Loan.Status.COMPLETED and expected != ZERO:
            yield f"Loan {loan.loan_id} is marked completed but ₦{expected:,.2f} is still owed"


def share_issues():
    for account in ShareAccount.objects.select_related('member'):
        approved = account.transactions.filter(status='APPROVED')
        shares = approved.aggregate(n=Sum('number_of_shares'))['n'] or 0
        value = _sum(approved, 'total_amount')
        if (account.total_shares, account.current_value) != (shares, value):
            yield (f"Shares {account.member.membership_id}: {account.total_shares} worth ₦{account.current_value:,.2f}, "
                   f"approved purchases say {shares} worth ₦{value:,.2f}")


class Command(BaseCommand):
    help = "Check savings, loan and share balances against their transactions (read-only)."

    def handle(self, *args, **options):
        problems = [*savings_issues(), *loan_issues(), *share_issues()]
        if not problems:
            self.stdout.write(self.style.SUCCESS("All savings, loan and share balances are consistent."))
            return
        for line in problems:
            self.stdout.write(self.style.ERROR(line))
        self.stdout.write(self.style.ERROR(f"{len(problems)} discrepancy(ies) found."))
        sys.exit(1)
