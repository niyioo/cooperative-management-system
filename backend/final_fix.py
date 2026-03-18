import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.members.models import Member
from apps.savings.models import SavingsAccount
from apps.loans.models import LoanProduct
from apps.shares.models import ShareAccount

def fix_all():
    print("🛠️ Starting System Repair...")

    # 1. Create a Default Loan Product (Matches your Frontend dropdown)
    product, created = LoanProduct.objects.get_or_create(
        name="Standard Term Loan",
        defaults={
            'interest_rate': Decimal('5.00'),
            'max_amount': Decimal('500000.00'),
            'max_duration_months': 24,
            'is_active': True
        }
    )
    if created: print("✅ Created 'Standard Term Loan' Product")

    # 2. Repair Savings and Share Accounts for all members
    members = Member.objects.all()
    print(f"👥 Found {members.count()} members. Checking wallets...")
    
    for member in members:
        # Fix Savings
        SavingsAccount.objects.get_or_create(member=member)
        # Fix Shares
        ShareAccount.objects.get_or_create(member=member)
        
    print("✅ All members now have Savings and Share accounts.")
    print("\n✨ REPAIR COMPLETE. Refresh your browser.")

if __name__ == "__main__":
    fix_all()