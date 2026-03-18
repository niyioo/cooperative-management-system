import os
import django
import uuid
from decimal import Decimal
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') 
django.setup()

from django.contrib.auth import get_user_model
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from apps.loans.models import Loan
from apps.finance.models import LedgerEntry
from apps.shares.models import ShareAccount

User = get_user_model()

def seed_database():
    print("🚀 Starting Database Seeding...")

    # 1. Create a Manager/Admin
    admin_email = "admin@bravedge.com"
    admin_user, created = User.objects.get_or_create(
        email=admin_email,
        defaults={
            'role': 'MANAGER',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    if created:
        admin_user.set_password('adminpass123')
        admin_user.save()
        print(f"✅ Admin User created: {admin_email}")

    # 2. Sample Data for Members
    member_data = [
        ("john.doe@gmail.com", "John", "Doe", "08011112222"),
        ("sarah.smith@yahoo.com", "Sarah", "Smith", "08033334444"),
        ("emeka.obi@gmail.com", "Emeka", "Obi", "08155556666"),
    ]

    for email, fname, lname, phone in member_data:
        # Create User (Auth only)
        user, user_created = User.objects.get_or_create(
            email=email,
            defaults={'role': 'MEMBER'}
        )
        if user_created:
            user.set_password('memberpass123')
            user.save()

        # Create Member Profile (Names live here!)
        member, mem_created = Member.objects.get_or_create(
            user=user,
            defaults={
                'first_name': fname,
                'last_name': lname,
                'phone_number': phone,
                'status': 'ACTIVE',
                'membership_id': f"COOP-{uuid.uuid4().hex[:6].upper()}"
            }
        )

        if mem_created:
            # 3. Create Savings Account & Initial Deposit
            savings, _ = SavingsAccount.objects.get_or_create(
                member=member,
                defaults={'balance': Decimal('0.00')}
            )
            deposit_amount = Decimal('50000.00')
            savings.balance += deposit_amount
            savings.save()

            # Record Savings in Global Ledger
            LedgerEntry.objects.create(
                type='INCOME',
                category='Monthly Savings',
                amount=deposit_amount,
                date=timezone.now().date(),
                description=f"Initial savings deposit for {fname} {lname} ({member.membership_id})",
                recorded_by=admin_user
            )

            # 4. Create Share Account
            ShareAccount.objects.get_or_create(
                member=member,
                defaults={'total_shares': 100, 'current_value': Decimal('10000.00')}
            )
            print(f"👤 Member seeded: {fname} {lname}")

    # 5. Create a Sample Loan for the first member found
    lucky_member = Member.objects.filter(first_name="John").first()
    if lucky_member:
        loan_amount = Decimal('200000.00')
        Loan.objects.create(
            member=lucky_member,
            principal_amount=loan_amount,
            balance_remaining=loan_amount,
            tenure_months=12,
            purpose="Business Expansion",
            status='ACTIVE',
            loan_id=f"LN-{uuid.uuid4().hex[:6].upper()}"
        )

        # Record Loan Disbursement as an Expense in Ledger
        LedgerEntry.objects.create(
            type='EXPENSE',
            category='Loan Disbursement',
            amount=loan_amount,
            date=timezone.now().date(),
            description=f"Loan disbursement to {lucky_member.first_name} {lucky_member.last_name}",
            recorded_by=admin_user
        )
        print(f"💰 Sample Loan created for {lucky_member.first_name}")

    print("\n✨ Seeding Complete! Everything is ready.")

if __name__ == "__main__":
    seed_database()