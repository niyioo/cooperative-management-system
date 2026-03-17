from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import ShareAccount, ShareTransaction
from .serializers import ShareAccountSerializer, ShareTransactionSerializer
from apps.accounts.permissions import IsManagerOrAdmin

class ShareAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShareAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return ShareAccount.objects.all()
        return ShareAccount.objects.filter(member__user=user)

class ShareTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = ShareTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return ShareTransaction.objects.all()
        return ShareTransaction.objects.filter(account__member__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        txn = self.get_object()
        if txn.status == ShareTransaction.Status.APPROVED:
            return Response({"detail": "Transaction already approved"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            txn.status = ShareTransaction.Status.APPROVED
            txn.approved_by = request.user
            txn.save()

            # Update Share Account
            account = txn.account
            account.total_shares += txn.shares_bought
            account.total_value += txn.total_amount
            account.save()

        return Response({"status": "Shares approved and ledger updated."})