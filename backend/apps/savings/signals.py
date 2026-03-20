from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import SavingsTransaction

@receiver(post_save, sender=SavingsTransaction)
def update_account_balance(sender, instance, created, **kwargs):
    # This triggers every time a transaction is saved.
    # We only care if the status was JUST changed to APPROVED.
    if instance.status == 'APPROVED':
        account = instance.account
        
        # Logic: We only apply the math once. 
        # (Advanced tip: Usually you'd check a 'is_processed' flag here)
        if instance.transaction_type in ['DEPOSIT', 'INTEREST', 'DIVIDEND']:
            account.balance += instance.amount
        elif instance.transaction_type == 'WITHDRAWAL':
            account.balance -= instance.amount
            
        account.save()