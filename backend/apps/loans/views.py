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
from apps.finance.models import LedgerEntry
# ✅ Added Savings imports so the API matches the Admin logic
from apps.savings.models import SavingsAccount, SavingsTransaction 

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
        """Moves loan to ACTIVE, credits Member Savings, and records Ledger Expense."""
        loan = self.get_object()
        if loan.status != Loan.Status.APPROVED:
            return Response({"detail": "Loan must be approved before disbursement."}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            loan.status = Loan.Status.ACTIVE
            loan.disbursed_at = timezone.now()
            loan.balance_remaining = loan.total_payable
            loan.save()

            # ✅ 1. Credit the Member's Savings Account (Matches Admin Logic)
            savings_account, _ = SavingsAccount.objects.get_or_create(member=loan.member)
            savings_account.balance += loan.principal_amount
            savings_account.save()

            SavingsTransaction.objects.create(
                account=savings_account,
                transaction_type='DEPOSIT',
                amount=loan.principal_amount,
                reference=f"DISB-{uuid.uuid4().hex[:6].upper()}",
                status='APPROVED',
                description=f"Automated Loan Disbursement for {loan.loan_id}",
                approved_by=request.user
            )
            
            # ✅ 2. Record the Coop's Cash Outflow
            LedgerEntry.objects.create(
                type='EXPENSE',
                category='Loan Disbursement',
                amount=loan.principal_amount,
                member=loan.member,
                description=f"Principal disbursement for Loan {loan.loan_id}",
                date=timezone.now().date()
            )
            
        return Response({"status": f"Loan {loan.loan_id} disbursed. Funds deposited to savings and ledger updated."})

    def destroy(self, request, *args, **kwargs):
        if not request.user.role in ['SUPER_ADMIN', 'MANAGER']:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        loan = self.get_object()
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
            
            # 1. Reduce the Loan Balance
            loan = repayment.loan
            loan.update_balance(repayment.amount_paid)

            # ✅ 2. AUTOMATIC LEDGER ENTRY: Record the Repayment as Income (Cash In)
            LedgerEntry.objects.create(
                type='INCOME',
                category='Loan Repayment',
                amount=repayment.amount_paid,
                member=loan.member,
                description=f"Repayment received for Loan {loan.loan_id}",
                date=timezone.now().date()
            )