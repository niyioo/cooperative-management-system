from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Sum

# Import serializers
from .serializers import (
    CustomTokenObtainPairSerializer, 
    UserSerializer, 
    RegisterUserSerializer
)

# Import models from other apps to build the summary
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from apps.loans.models import Loan
from apps.shares.models import ShareAccount
from apps.finance.models import LedgerEntry

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    """Handles login and returns custom JWT claims (email, role)."""
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    """Handles new user registration and auto-creates a Member profile."""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterUserSerializer

class UserProfileView(generics.RetrieveAPIView):
    """Returns basic Auth user data for the current logged-in user."""
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class MemberSummaryView(generics.GenericAPIView):
    """
    The Dashboard Engine.
    Aggregates financial data across Savings, Loans, and Shares 
    for the logged-in member.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # 1. Get the member record linked to this user
        # We use related_name='member_profile' defined in the Member model
        member = get_object_or_404(Member, user=request.user)
        
        # 2. Query Savings Balance
        savings = SavingsAccount.objects.filter(member=member).first()
        savings_balance = savings.balance if savings else 0
        
        # 3. Query Shares Data
        shares = ShareAccount.objects.filter(member=member).first()
        shares_value = shares.current_value if shares else 0
        shares_count = shares.total_shares if shares else 0
        
        # 4. Query Outstanding Loan Balance
        # Sums up the remaining balance of all ACTIVE loans for this member
        active_loans_total = Loan.objects.filter(
            member=member, 
            status='ACTIVE'
        ).aggregate(total=Sum('balance_remaining'))['total'] or 0
        
        # 5. Get Recent Activity
        # We search the ledger for entries mentioning this member's ID
        # (Alternatively, filter by a member FK if you added one to LedgerEntry)
        recent_tx_qs = LedgerEntry.objects.filter(
            description__icontains=member.membership_id
        ).order_by('-date')[:5]

        data = {
            "membership_id": member.membership_id,
            "status": member.status,
            "savings_balance": savings_balance,
            "shares_value": shares_value,
            "shares_count": shares_count,
            "active_loan_balance": active_loans_total,
            "pending_dues": 0, # Placeholder for future Contributions app integration
            "recent_transactions": [
                {
                    "id": tx.id,
                    "type": tx.type,
                    "amount": tx.amount,
                    "date": tx.date,
                    "description": tx.description,
                    "reference_id": tx.reference_id
                } for tx in recent_tx_qs
            ]
        }
        
        return Response(data, status=status.HTTP_200_OK)