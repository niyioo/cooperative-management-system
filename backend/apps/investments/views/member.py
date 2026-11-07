"""/api/v1/me/investments/"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin, member_scoped
from apps.common.serializers import money_to_str
from apps.ledger.choices import TransactionStatus
from apps.ledger.models import Transaction
from apps.ledger.serializers import TransactionSerializer

from ..models import InvestmentAccount
from ..selectors import member_investment_position


class MyInvestmentsView(MemberAPIMixin, APIView):
    @extend_schema(responses={200: OpenApiResponse(description="Investment accounts and total principal")})
    def get(self, request):
        return Response(money_to_str(member_investment_position(self.member)))


class MyInvestmentTransactionsView(MemberAPIMixin, ListAPIView):
    serializer_class = TransactionSerializer

    @member_scoped(Transaction)
    def get_queryset(self):
        account = get_object_or_404(InvestmentAccount, pk=self.kwargs["account_id"], member=self.member)
        return (
            account.transactions.exclude(status=TransactionStatus.REJECTED)
            .select_related("investment_account__product")
            .order_by("-value_date", "-created_at")
        )
