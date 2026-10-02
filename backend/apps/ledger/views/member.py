"""/api/v1/me/transactions/ — the member's own transaction history and statements (BR-10)."""
import django_filters
from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.serializers import ValidationError
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin, member_scoped
from apps.audit.services import record

from ..choices import TransactionStatus, TransactionType
from ..models import Transaction
from ..selectors import member_transactions
from ..serializers import TransactionSerializer
from ..statements import build_pdf, build_xlsx


class MyTransactionFilter(django_filters.FilterSet):
    txn_type = django_filters.MultipleChoiceFilter(choices=TransactionType.choices)
    date_from = django_filters.DateFilter(field_name="value_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="value_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Transaction
        fields = ["txn_type"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(reference__icontains=value) | Q(description__icontains=value) | Q(external_reference__icontains=value))


class MyTransactionsView(MemberAPIMixin, ListAPIView):
    serializer_class = TransactionSerializer
    filterset_class = MyTransactionFilter
    filter_backends = [django_filters.rest_framework.DjangoFilterBackend]

    @member_scoped(Transaction)
    def get_queryset(self):
        # Rejected entries never happened as far as the member is concerned.
        return member_transactions(self.member).exclude(status=TransactionStatus.REJECTED)


class StatementView(MemberAPIMixin, APIView):
    FORMATS = {
        "pdf": ("application/pdf", build_pdf),
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", build_xlsx),
    }

    @extend_schema(
        parameters=[
            OpenApiParameter("format", str, enum=["pdf", "xlsx"], description="Default pdf"),
            OpenApiParameter("date_from", str, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, description="YYYY-MM-DD"),
        ],
        responses={(200, "application/pdf"): OpenApiResponse(description="Statement file")},
    )
    def get(self, request):
        fmt = request.query_params.get("format", "pdf")
        if fmt not in self.FORMATS:
            raise ValidationError({"format": ["Use pdf or xlsx."]})
        dates = MyTransactionFilter(request.query_params).form
        if not dates.is_valid():
            raise ValidationError(dates.errors)
        date_from, date_to = dates.cleaned_data.get("date_from"), dates.cleaned_data.get("date_to")
        content_type, builder = self.FORMATS[fmt]
        member = self.member
        response = HttpResponse(builder(member, date_from, date_to), content_type=content_type)
        filename = f"statement-{member.membership_number.replace('/', '-')}.{fmt}"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Cache-Control"] = "no-store"
        record("member.statement_downloaded", actor=request.user, obj=member, metadata={"format": fmt})
        return response
