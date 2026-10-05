"""/api/v1/me/dividends/ — published cycles only (BR-09)."""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin
from apps.common.serializers import money_to_str

from ..selectors import member_dividend_history


class MyDividendsView(MemberAPIMixin, APIView):
    @extend_schema(responses={200: OpenApiResponse(description="Dividend history for published cycles")})
    def get(self, request):
        return Response(money_to_str(member_dividend_history(self.member, published_only=True)))
