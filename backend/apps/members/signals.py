from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from apps.savings.models import SavingsAccount
from .models import Member

User = get_user_model()

@receiver(post_save, sender=User)
def create_member_profile(sender, instance, created, **kwargs):
    if created:
        # This ensures every new user (Member or Admin) gets a profile row
        # We use defaults for names since we only have the email at registration
        Member.objects.create(
            user=instance,
            first_name="New",
            last_name="Member",
            phone_number=f"0000{instance.id.hex[:6]}" # Temporary placeholder
        )

@receiver(post_save, sender=Member)
def create_member_savings_account(sender, instance, created, **kwargs):
    if created:
        # Automatically create a savings account when a new member profile is created
        SavingsAccount.objects.get_or_create(member=instance)