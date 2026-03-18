import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.members.models import Member
from apps.savings.models import SavingsAccount

def repair_accounts():
    members = Member.objects.all()
    created_count = 0
    
    for member in members:
        # get_or_create ensures we don't create duplicates
        account, created = SavingsAccount.objects.get_or_create(
            member=member,
            defaults={'balance': 0.00}
        )
        if created:
            created_count += 1
            print(f"✅ Created savings account for {member.first_name}")

    print(f"✨ Done! Created {created_count} missing accounts.")

if __name__ == "__main__":
    repair_accounts()