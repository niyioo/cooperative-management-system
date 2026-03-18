import uuid
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from decimal import Decimal

from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment
from .serializers import LoanProductSerializer, LoanSerializer, LoanGuarantorSerializer, LoanRepaymentSerializer
from apps.accounts.permissions import IsManagerOrAdmin, IsLoanOfficer 
from apps.finance.models import LedgerEntry # Ensure this import exists

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
        queryset = Loan.objects.select_related('member', 'loan_product').all().order_by('-created_at')
        
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'LOAN_OFFICER']:
            return queryset
        return queryset.filter(member__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def approve(self, request, pk=None):
        loan = self.get_object()
        if loan.status != Loan.Status.PENDING:
            return Response({"detail": "Only pending loans can be approved."}, status=status.HTTP_400_BAD_REQUEST)
        
        loan.status = Loan.Status.APPROVED
        loan.approved_by = request.user
        loan.save()
        return Response({"status": f"Loan {loan.loan_id} approved. Awaiting disbursement."})

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def reject(self, request, pk=None):
        loan = self.get_object()
        if loan.status != Loan.Status.PENDING:
            return Response({"detail": "Only pending loans can be rejected."}, status=status.HTTP_400_BAD_REQUEST)
        
        loan.status = Loan.Status.REJECTED
        loan.save()
        return Response({"status": "Loan application has been rejected."})

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def disburse(self, request, pk=None):
        """Moves loan to ACTIVE and records the cash outflow in the Ledger."""
        loan = self.get_object()
        if loan.status != Loan.Status.APPROVED:
            return Response({"detail": "Loan must be approved before disbursement."}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            loan.status = Loan.Status.ACTIVE
            loan.disbursed_at = timezone.now()
            
            # Ensure balance is initialized to total payable amount
            loan.balance_remaining = loan.total_payable
            loan.save()
            
            # ✅ AUTOMATIC LEDGER ENTRY: Record the disbursement as an Expense (Cash Out)
            LedgerEntry.objects.create(
                type='EXPENSE',
                category='Loan Disbursement',
                amount=loan.principal_amount,
                member=loan.member,
                description=f"Principal disbursement for Loan {loan.loan_id}",
                date=timezone.now().date()
            )
            
        return Response({"status": f"Loan {loan.loan_id} is now active and disbursement recorded."})

    def destroy(self, request, *args, **kwargs):
        """Allows Managers to delete loan records (use with caution)."""
        if not request.user.role in ['SUPER_ADMIN', 'MANAGER']:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        loan = self.get_object()
        # Prevent deletion of active loans with a balance to maintain audit integrity
        if loan.status == Loan.Status.ACTIVE and loan.balance_remaining > 0:
            return Response({"detail": "Cannot delete an active loan with an outstanding balance."}, status=status.HTTP_400_BAD_REQUEST)
            
        return super().destroy(request, *args, **kwargs)

class LoanRepaymentViewSet(viewsets.ModelViewSet):
    serializer_class = LoanRepaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT', 'LOAN_OFFICER']:
            return LoanRepayment.objects.all().order_by('-payment_date')
        return LoanRepayment.objects.filter(loan__member__user=user).order_by('-payment_date')

    def perform_create(self, serializer):
        with transaction.atomic():
            repayment = serializer.save(
                receipt_reference=f"REP-{uuid.uuid4().hex[:8].upper()}",
                received_by=self.request.user
            )
            
            # Update the specific loan balance via helper method
            loan = repayment.loan
            loan.update_balance(repayment.amount_paid)