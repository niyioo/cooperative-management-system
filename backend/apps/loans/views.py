import uuid
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment
from .serializers import LoanProductSerializer, LoanSerializer, LoanGuarantorSerializer, LoanRepaymentSerializer
from apps.accounts.permissions import IsManagerOrAdmin, IsLoanOfficer

class LoanProductViewSet(viewsets.ModelViewSet):
    queryset = LoanProduct.objects.all()
    serializer_class = LoanProductSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManagerOrAdmin()]
        return [permissions.IsAuthenticated()]

class LoanViewSet(viewsets.ModelViewSet):
    serializer_class = LoanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER']:
            return Loan.objects.all()
        return Loan.objects.filter(member__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def approve(self, request, pk=None):
        loan = self.get_object()
        if loan.status != Loan.Status.PENDING:
            return Response({"detail": "Only pending loans can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        
        loan.status = Loan.Status.APPROVED
        loan.approved_by = request.user
        loan.save()
        return Response({"status": "Loan approved successfully. Awaiting disbursement."})

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def disburse(self, request, pk=None):
        loan = self.get_object()
        if loan.status != Loan.Status.APPROVED:
            return Response({"detail": "Loan must be approved before disbursement."}, status=status.HTTP_400_BAD_REQUEST)
        
        loan.status = Loan.Status.ACTIVE
        loan.disbursed_at = timezone.now()
        loan.save()
        return Response({"status": "Loan marked as active and disbursed."})

class LoanRepaymentViewSet(viewsets.ModelViewSet):
    serializer_class = LoanRepaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT', 'LOAN_OFFICER']:
            return LoanRepayment.objects.all()
        return LoanRepayment.objects.filter(loan__member__user=user)

    def perform_create(self, serializer):
        with transaction.atomic():
            repayment = serializer.save(
                receipt_reference=f"REP-{uuid.uuid4().hex[:8].upper()}",
                received_by=self.request.user
            )
            # Deduct from loan balance
            loan = repayment.loan
            loan.balance_remaining -= repayment.amount_paid
            if loan.balance_remaining <= 0:
                loan.balance_remaining = 0
                loan.status = Loan.Status.COMPLETED
            loan.save()