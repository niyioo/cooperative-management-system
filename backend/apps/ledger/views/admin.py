"""/api/v1/admin/transactions/ and /api/v1/admin/batches/"""
import django_filters
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.accounts.permissions import AnyPerm, OfficerAPIMixin
from apps.accounts.perms import P
from apps.common.fields import MoneyField
from apps.common.serializers import money_to_str
from apps.common.parsers import UPLOAD_PARSERS

from .. import corrections, services
from ..batches import get_handler
from ..choices import BatchStatus, BatchType, EntrySide, TransactionStatus, TransactionType
from ..models import Transaction, TransactionBatch
from ..selectors import ZERO
from ..serializers import AdjustmentSerializer, BatchSerializer, BatchUploadSerializer, LedgerEntrySerializer, ReasonSerializer

UUID_RE = r"[0-9a-fA-F-]{36}"


class TransactionFilter(django_filters.FilterSet):
    member = django_filters.UUIDFilter(field_name="member_id")
    txn_type = django_filters.MultipleChoiceFilter(choices=TransactionType.choices)
    status = django_filters.MultipleChoiceFilter(choices=TransactionStatus.choices)
    batch = django_filters.UUIDFilter(field_name="batch_id")
    date_from = django_filters.DateFilter(field_name="value_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="value_date", lookup_expr="lte")

    class Meta:
        model = Transaction
        fields = ["member", "txn_type", "status", "batch"]


class TransactionViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LedgerEntrySerializer
    filterset_class = TransactionFilter
    lookup_value_regex = UUID_RE
    search_fields = ["reference", "external_reference", "description", "member__membership_number", "member__last_name"]
    ordering_fields = ["value_date", "created_at", "amount"]
    permission_map = {
        "list": (P.VIEW_ALL_TRANSACTIONS,),
        "retrieve": (P.VIEW_ALL_TRANSACTIONS,),
        "pending": AnyPerm(P.APPROVE_TRANSACTION, P.VIEW_ALL_TRANSACTIONS),
        "approve": (P.APPROVE_TRANSACTION,),
        "reject": (),  # the creator may cancel their own entry; the service checks everyone else
        "reverse": (P.REVERSE_TRANSACTION,),
        "adjustments": (P.POST_ADJUSTMENT,),
        "summary": (P.VIEW_ALL_TRANSACTIONS,),
    }

    def get_queryset(self):
        return Transaction.objects.select_related(
            "member",
            "savings_account__product",
            "savings_account__cycle",
            "loan",
            "investment_account__product",
            "created_by",
            "approved_by",
            "batch",
        ).order_by("-value_date", "-created_at")

    def get_object(self):
        # Rejecting is open to any officer (creators cancel their own entries), so
        # scope the lookup: without view_all_transactions you can only reach your own.
        if self.action == "reject" and not self.request.user.has_perm(P.VIEW_ALL_TRANSACTIONS):
            entry = self.get_queryset().filter(pk=self.kwargs["pk"], created_by=self.request.user).first()
            if entry is None:
                raise NotFound()
            return entry
        return super().get_object()

    @extend_schema(responses={200: LedgerEntrySerializer(many=True)}, summary="Single entries awaiting a second officer")
    @action(detail=False, methods=["get"])
    def pending(self, request):
        queryset = self.get_queryset().filter(status=TransactionStatus.PENDING, batch__isnull=True)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(LedgerEntrySerializer(page, many=True).data)

    @extend_schema(request=None, responses={200: LedgerEntrySerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        entry = services.approve_entry(request.user, self.get_object())
        return Response(LedgerEntrySerializer(self.get_queryset().get(pk=entry.pk)).data)

    @extend_schema(request=ReasonSerializer, responses={200: LedgerEntrySerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.reject_entry(request.user, self.get_object(), **serializer.validated_data)
        return Response(LedgerEntrySerializer(self.get_queryset().get(pk=entry.pk)).data)

    @extend_schema(request=ReasonSerializer, responses={201: LedgerEntrySerializer}, summary="Create a reversal of a posted entry")
    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reversal = corrections.reverse_entry(request.user, self.get_object(), **serializer.validated_data)
        return Response(LedgerEntrySerializer(self.get_queryset().get(pk=reversal.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=AdjustmentSerializer, responses={201: LedgerEntrySerializer}, summary="Adjust a savings or investment balance")
    @action(detail=False, methods=["post"])
    def adjustments(self, request):
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = corrections.post_adjustment(request.user, **serializer.validated_data)
        return Response(LedgerEntrySerializer(self.get_queryset().get(pk=entry.pk)).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: OpenApiResponse(description="Posted totals by transaction type for the filtered period")})
    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(status__in=[TransactionStatus.POSTED, TransactionStatus.REVERSED])
        rows = (
            queryset.order_by()
            .values("txn_type")
            .annotate(
                count=Count("id"),
                credits=Coalesce(Sum("amount", filter=Q(entry_side=EntrySide.CREDIT)), Value(ZERO), output_field=MoneyField()),
                debits=Coalesce(Sum("amount", filter=Q(entry_side=EntrySide.DEBIT)), Value(ZERO), output_field=MoneyField()),
            )
            .order_by("txn_type")
        )
        data = [{**row, "label": TransactionType(row["txn_type"]).label} for row in rows]
        return Response(money_to_str({"by_type": data, "entries": sum(r["count"] for r in data)}))


class BatchFilter(django_filters.FilterSet):
    batch_type = django_filters.ChoiceFilter(choices=BatchType.choices)
    status = django_filters.MultipleChoiceFilter(choices=BatchStatus.choices)

    class Meta:
        model = TransactionBatch
        fields = ["batch_type", "status"]


class BatchViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    parser_classes = UPLOAD_PARSERS  # create receives a file
    serializer_class = BatchSerializer
    filterset_class = BatchFilter
    lookup_value_regex = UUID_RE
    search_fields = ["reference", "description"]
    permission_map = {
        "list": AnyPerm(P.MANAGE_BATCHES, P.APPROVE_BATCH),
        "retrieve": AnyPerm(P.MANAGE_BATCHES, P.APPROVE_BATCH),
        "lines": AnyPerm(P.MANAGE_BATCHES, P.APPROVE_BATCH),
        "create": (P.MANAGE_BATCHES,),
        "template": (P.MANAGE_BATCHES,),
        "submit": (P.MANAGE_BATCHES,),
        "approve": (P.APPROVE_BATCH,),
        "reject": AnyPerm(P.MANAGE_BATCHES, P.APPROVE_BATCH),
    }

    def get_queryset(self):
        return TransactionBatch.objects.select_related("created_by", "approved_by")

    @extend_schema(request={"multipart/form-data": BatchUploadSerializer}, responses={201: BatchSerializer})
    def create(self, request):
        serializer = BatchUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        batch = services.create_batch_from_file(
            request.user,
            batch_type=data["batch_type"],
            file=data["file"],
            options={"product": data["product"], "period": data["period"]},
            description=data["description"],
        )
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: LedgerEntrySerializer(many=True)})
    @action(detail=True, methods=["get"])
    def lines(self, request, pk=None):
        entries = (
            self.get_object()
            .transactions.select_related("member", "savings_account__product", "savings_account__cycle", "created_by", "approved_by")
            .order_by("member__last_name")
        )
        page = self.paginate_queryset(entries)
        return self.get_paginated_response(LedgerEntrySerializer(page, many=True).data)

    @extend_schema(request=None, responses={200: BatchSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return Response(BatchSerializer(services.submit_batch(request.user, self.get_object())).data)

    @extend_schema(request=None, responses={200: BatchSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return Response(BatchSerializer(services.approve_batch(request.user, self.get_object())).data)

    @extend_schema(request=ReasonSerializer, responses={200: BatchSerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = services.reject_batch(request.user, self.get_object(), **serializer.validated_data)
        return Response(BatchSerializer(batch).data)

    @extend_schema(
        parameters=[OpenApiParameter("type", str, required=True, description="Batch type, e.g. CONTRIBUTIONS")],
        responses={(200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiResponse(description="Excel template")},
    )
    @action(detail=False, methods=["get"])
    def template(self, request):
        batch_type = request.query_params.get("type", "")
        content = get_handler(batch_type).template()
        if content is None:
            raise NotFound("This batch type has no upload template.")
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="emdi-{batch_type.lower()}-template.xlsx"'
        return response
