from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db import transaction
from .models import ShareAccount, ShareTransaction
from .serializers import ShareAccountSerializer, ShareTransactionSerializer
from apps.accounts.permissions import IsManagerOrAdmin # Update path if needed

class ShareAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShareAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ShareAccount.objects.select_related('member').all()
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return queryset
        return queryset.filter(member__user=user)

class ShareTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = ShareTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return ShareTransaction.objects.all()
        return ShareTransaction.objects.filter(account__member__user=user)

    def perform_create(self, serializer):
        user = self.request.user
        
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            account = serializer.validated_data.get('account')
            txn_status = ShareTransaction.Status.APPROVED
            approved_by = user
        else:
            account = ShareAccount.objects.get(member__user=user)
            txn_status = ShareTransaction.Status.PENDING
            approved_by = None

        with transaction.atomic():
            txn = serializer.save(
                account=account,
                status=txn_status,
                approved_by=approved_by
            )
            
            # Auto-update if Manager creates it
            if txn.status == ShareTransaction.Status.APPROVED:
                account.total_shares += txn.number_of_shares
                account.current_value += txn.total_amount
                account.save()

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        txn = self.get_object()
        if txn.status == ShareTransaction.Status.APPROVED:
            return Response({"detail": "Transaction already approved"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            txn.status = ShareTransaction.Status.APPROVED
            txn.approved_by = request.user
            txn.save()

            account = txn.account
            account.total_shares += txn.number_of_shares
            account.current_value += txn.total_amount
            account.save()

        return Response({"status": "Shares approved and ledger updated."})

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def reject(self, request, pk=None):
        """Allows Admins to reject a pending share purchase."""
        txn = self.get_object()
        if txn.status != ShareTransaction.Status.PENDING:
            return Response({"detail": "Only pending requests can be rejected."}, status=status.HTTP_400_BAD_REQUEST)

        txn.status = ShareTransaction.Status.REJECTED
        txn.save()
        return Response({"status": "Share purchase request rejected."})