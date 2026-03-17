from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from apps.loans.models import Loan
from apps.shares.models import ShareAccount
from apps.finance.models import Income, Expense
from decimal import Decimal

class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # If regular member, return personal summary
        if user.role == 'MEMBER':
            member = getattr(user, 'member_profile', None)
            if not member:
                return Response({"detail": "Profile not found"}, status=404)
            
            savings = SavingsAccount.objects.filter(member=member).aggregate(total=Sum('balance'))['total'] or 0
            shares = ShareAccount.objects.filter(member=member).aggregate(total=Sum('total_value'))['total'] or 0
            active_loans = Loan.objects.filter(member=member, status='ACTIVE').aggregate(total=Sum('balance_remaining'))['total'] or 0

            return Response({
                "role": "MEMBER",
                "total_savings": savings,
                "total_shares_value": shares,
                "outstanding_loan_balance": active_loans
            })

        # If Admin/Manager, return global summary
        total_members = Member.objects.count()
        active_members = Member.objects.filter(status='ACTIVE').count()
        
        total_savings = SavingsAccount.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        total_shares = ShareAccount.objects.aggregate(total=Sum('total_value'))['total'] or Decimal('0.00')
        
        total_loans_disbursed = Loan.objects.filter(status__in=['ACTIVE', 'COMPLETED']).aggregate(total=Sum('principal_amount'))['total'] or Decimal('0.00')
        outstanding_loans = Loan.objects.filter(status='ACTIVE').aggregate(total=Sum('balance_remaining'))['total'] or Decimal('0.00')
        
        total_income = Income.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        net_profit = total_income - total_expenses

        return Response({
            "role": "ADMIN",
            "members": {
                "total": total_members,
                "active": active_members
            },
            "financials": {
                "total_savings": total_savings,
                "total_shares": total_shares,
                "total_loans_disbursed": total_loans_disbursed,
                "outstanding_loans": outstanding_loans,
                "coop_income": total_income,
                "coop_expenses": total_expenses,
                "net_profit": net_profit
            }
        })