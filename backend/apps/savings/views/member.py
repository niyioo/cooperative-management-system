"""/api/v1/me/savings/ — view-only. There is deliberately no withdrawal endpoint (BR-01)."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin, member_scoped
from apps.common.serializers import money_to_str
from apps.ledger.choices import TransactionStatus
from apps.ledger.models import Transaction
from apps.ledger.serializers import TransactionSerializer

from ..models import ProductKind, SavingsAccount
from ..selectors import cycle_grid, member_savings_position


class MySavingsView(MemberAPIMixin, APIView):
    @extend_schema(responses={200: OpenApiResponse(description="Christmas savings, other savings and total")})
    def get(self, request):
        return Response(money_to_str(member_savings_position(self.member)))


class MyChristmasSavingsView(MemberAPIMixin, APIView):
    @extend_schema(
        parameters=[OpenApiParameter("year", int, description="Defaults to the current year, else the latest cycle")],
        responses={200: OpenApiResponse(description="January–October contributions for the year")},
    )
    def get(self, request):
        accounts = SavingsAccount.objects.filter(member=self.member, product__kind=ProductKind.CYCLE).select_related("cycle", "member")
        year = request.query_params.get("year")
        if year:
            account = accounts.filter(cycle__year=year).first()
        else:
            account = accounts.filter(cycle__year=timezone.localdate().year).first() or accounts.order_by("-cycle__year").first()
        if account is None:
            raise NotFound("No Christmas Savings for that year.")
        grid = cycle_grid(account.cycle, [account])
        row = grid["rows"][0]
        years = sorted(accounts.values_list("cycle__year", flat=True).distinct(), reverse=True)
        return Response(
            money_to_str(
                {
                    "cycle": grid["cycle"],
                    "year": account.cycle.year,
                    "account_number": account.account_number,
                    "months": grid["months"],
                    "contributions": row["months"],
                    "other": row["other"],
                    "total": row["total"],
                    "paid_out": row["paid_out"],
                    "expected_monthly": row["expected_monthly"],
                    "expected_total": row["expected_total"],
                    "years": years,
                }
            )
        )


class MySavingsTransactionsView(MemberAPIMixin, ListAPIView):
    serializer_class = TransactionSerializer

    @member_scoped(Transaction)
    def get_queryset(self):
        account = get_object_or_404(SavingsAccount, pk=self.kwargs["account_id"], member=self.member)
        return (
            account.transactions.exclude(status=TransactionStatus.REJECTED)
            .select_related("savings_account__product", "savings_account__cycle")
            .order_by("-value_date", "-created_at")
        )
