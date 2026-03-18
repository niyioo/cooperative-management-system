import uuid
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import SavingsAccount, SavingsTransaction
from .serializers import SavingsAccountSerializer, SavingsTransactionSerializer
# Assuming you have this permission, otherwise use permissions.IsAuthenticated
from apps.accounts.permissions import IsManagerOrAdmin 

class SavingsAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SavingsAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return SavingsAccount.objects.all().select_related('member')
        return SavingsAccount.objects.filter(member__user=user).select_related('member')

class SavingsTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return SavingsTransaction.objects.all()
        return SavingsTransaction.objects.filter(account__member__user=user)

    def perform_create(self, serializer):
        user = self.request.user
        
        # 1. Determine which account to post to
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            # Admins can post to the account provided in the payload (from the React Modal)
            account = serializer.validated_data.get('account')
        else:
            # Members can ONLY post to their own account
            account = SavingsAccount.objects.get(member__user=user)
        
        # 2. Generate Reference (use provided, or generate one)
        reference = self.request.data.get('reference')
        if not reference:
            reference = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        
        # 3. Handle Auto-Approval for Admins
        txn_status = SavingsTransaction.Status.PENDING
        approved_by = None
        
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            txn_status = SavingsTransaction.Status.APPROVED
            approved_by = user

        # Wrap the save and balance update in an atomic block
        with transaction.atomic():
            txn = serializer.save(
                account=account, 
                reference=reference, 
                status=txn_status, 
                approved_by=approved_by
            )
            
            # If auto-approved by admin, update the wallet balance instantly
            if txn.status == SavingsTransaction.Status.APPROVED:
                if txn.transaction_type in [SavingsTransaction.TransactionType.DEPOSIT, SavingsTransaction.TransactionType.DIVIDEND, SavingsTransaction.TransactionType.INTEREST]:
                    account.balance += txn.amount
                elif txn.transaction_type == SavingsTransaction.TransactionType.WITHDRAWAL:
                    # Optional: Check for sufficient balance here if you want to block admin overdrafts
                    account.balance -= txn.amount
                account.save()

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        """Allows Admins to manually approve pending member requests."""
        txn = self.get_object()
        if txn.status == SavingsTransaction.Status.APPROVED:
            return Response({"detail": "Transaction already approved"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            txn.status = SavingsTransaction.Status.APPROVED
            txn.approved_by = request.user
            txn.save()

            # Update Account Balance Safely
            account = txn.account
            if txn.transaction_type in [SavingsTransaction.TransactionType.DEPOSIT, SavingsTransaction.TransactionType.DIVIDEND, SavingsTransaction.TransactionType.INTEREST]:
                account.balance += txn.amount
            elif txn.transaction_type == SavingsTransaction.TransactionType.WITHDRAWAL:
                if account.balance < txn.amount:
                    return Response({"detail": "Insufficient balance for withdrawal"}, status=status.HTTP_400_BAD_REQUEST)
                account.balance -= txn.amount
            account.save()

        return Response({"status": "Transaction approved and balance updated."})