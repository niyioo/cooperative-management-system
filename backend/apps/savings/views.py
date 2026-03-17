import uuid
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import SavingsAccount, SavingsTransaction
from .serializers import SavingsAccountSerializer, SavingsTransactionSerializer
from apps.accounts.permissions import IsManagerOrAdmin

class SavingsAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SavingsAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return SavingsAccount.objects.all()
        return SavingsAccount.objects.filter(member__user=user)

class SavingsTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return SavingsTransaction.objects.all()
        return SavingsTransaction.objects.filter(account__member__user=user)

    def perform_create(self, serializer):
        # Generate a unique reference
        reference = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        account = SavingsAccount.objects.get(member__user=self.request.user)
        
        # If it's a deposit via transfer/card, it might be pending verification
        # If it's a withdrawal request, it goes to pending for admin approval
        serializer.save(account=account, reference=reference)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
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