from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.loans.models import Loan
from apps.savings.models import SavingsAccount # Adjust based on your actual model names
from .models import Notification

@receiver(post_save, sender=Loan)
def create_loan_notification(sender, instance, created, **kwargs):
    if created:
        Notification.objects.create(
            user=instance.member.user, # Notify the member
            type=Notification.TypeChoices.INFO,
            title="Loan Request Received",
            message=f"Your request for ₦{instance.principal} is being reviewed."
        )
    elif instance.status == 'APPROVED':
        Notification.objects.create(
            user=instance.member.user,
            type=Notification.TypeChoices.SUCCESS,
            title="Loan Approved! 🎉",
            message=f"Your loan of ₦{instance.principal} has been approved."
        )

# Register this in your apps.py (Ready method)