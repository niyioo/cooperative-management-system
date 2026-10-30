from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth_cookies import clear_refresh_cookie, get_refresh_cookie, require_json, set_refresh_cookie
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
    """
    POST {email, password} → {access, user}. The refresh token is set as an
    httpOnly cookie (never readable by page scripts) and left out of the body.
    """
    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = 'login'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            set_refresh_cookie(response, response.data.pop('refresh'))
        return response


class CookieTokenRefreshView(APIView):
    """POST {} → {access}, using and rotating the refresh cookie."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'token_refresh'
    throttle_classes = [ScopedRateThrottle]

    def post(self, request):
        require_json(request)
        token = get_refresh_cookie(request)
        # 401 (not 403) so the dashboard knows to send the user to sign in again.
        if not token:
            return Response({'detail': 'No active session.'}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={'refresh': token})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            response = Response({'detail': 'Your session has ended. Please sign in again.'},
                                status=status.HTTP_401_UNAUTHORIZED)
            clear_refresh_cookie(response)
            return response
        data = dict(serializer.validated_data)
        response = Response({'access': data['access']})
        if 'refresh' in data:
            set_refresh_cookie(response, data['refresh'])
        return response


class LogoutView(APIView):
    """POST {} → revokes the refresh token and clears the cookie."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        require_json(request)
        token = get_refresh_cookie(request)
        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                pass  # already expired or revoked
        response = Response({'detail': 'Signed out.'})
        clear_refresh_cookie(response)
        return response


class RegisterView(generics.CreateAPIView):
    """Public sign-up: creates a MEMBER whose profile waits for approval."""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterUserSerializer
    throttle_scope = 'register'
    throttle_classes = [ScopedRateThrottle]

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