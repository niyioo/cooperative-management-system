"""/api/v1/admin/dividends/cycles/ — the December dividend cycle."""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.ledger.serializers import BatchSerializer, ReasonSerializer

from .. import services
from ..models import DividendCycle, MemberDividend
from ..serializers import (
    DividendCycleSerializer,
    DividendCycleWriteSerializer,
    MemberDividendSerializer,
    PaySerializer,
    RunSerializer,
)

UUID_RE = r"[0-9a-fA-F-]{36}"


class DividendCycleViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = DividendCycleSerializer
    lookup_value_regex = UUID_RE
    filterset_fields = ["status", "financial_year"]
    permission_map = {
        "list": (P.VIEW_DIVIDENDS,),
        "retrieve": (P.VIEW_DIVIDENDS,),
        "runs": (P.VIEW_DIVIDENDS,),
        "member_dividends": (P.VIEW_DIVIDENDS,),
        "create": (P.MANAGE_DIVIDEND_CYCLES,),
        "partial_update": (P.MANAGE_DIVIDEND_CYCLES,),
        "cancel": (P.MANAGE_DIVIDEND_CYCLES,),
        "calculate": (P.CALCULATE_DIVIDENDS,),
        "approve": (P.APPROVE_DIVIDENDS,),
        "publish": (P.APPROVE_DIVIDENDS,),
        "pay": (P.PAY_DIVIDENDS, P.MANAGE_BATCHES),
    }

    def get_queryset(self):
        return DividendCycle.objects.select_related("approved_run__run_by", "approved_by").prefetch_related(
            "eligible_investment_products", "eligible_savings_products"
        )

    def _read(self, cycle):
        return DividendCycleSerializer(self.get_queryset().get(pk=cycle.pk)).data

    @extend_schema(request=DividendCycleWriteSerializer, responses={201: DividendCycleSerializer})
    def create(self, request):
        serializer = DividendCycleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = services.create_cycle(request.user, **serializer.validated_data)
        return Response(self._read(cycle), status=status.HTTP_201_CREATED)

    @extend_schema(request=DividendCycleWriteSerializer, responses={200: DividendCycleSerializer})
    def partial_update(self, request, pk=None):
        serializer = DividendCycleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("financial_year", None)
        cycle = services.update_cycle(request.user, self.get_object(), **data)
        return Response(self._read(cycle))

    @extend_schema(request=None, responses={200: DividendCycleSerializer})
    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        cycle = self.get_object()
        _, warning = services.calculate(request.user, cycle)
        data = self._read(cycle)
        data["warning"] = warning
        return Response(data)

    @extend_schema(request=None, responses={200: DividendCycleSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return Response(self._read(services.approve(request.user, self.get_object())))

    @extend_schema(request=None, responses={200: DividendCycleSerializer})
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        return Response(self._read(services.publish(request.user, self.get_object())))

    @extend_schema(request=PaySerializer, responses={201: BatchSerializer})
    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        serializer = PaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = services.prepare_payment(request.user, self.get_object(), **serializer.validated_data)
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ReasonSerializer, responses={200: DividendCycleSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._read(services.cancel_cycle(request.user, self.get_object(), **serializer.validated_data)))

    @extend_schema(responses={200: RunSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None, filter_backends=[])
    def runs(self, request, pk=None):
        return Response(RunSerializer(self.get_object().runs.select_related("run_by").order_by("-run_number"), many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("run", str, description="Run id; defaults to the approved run, else the latest")],
        responses={200: MemberDividendSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="member-dividends")
    def member_dividends(self, request, pk=None):
        cycle = self.get_object()
        run_id = request.query_params.get("run")
        run = cycle.runs.filter(pk=run_id).first() if run_id else (cycle.approved_run or cycle.runs.order_by("-run_number").first())
        rows = MemberDividend.objects.filter(run=run).select_related("member", "payment_transaction").order_by(
            "member__last_name", "member__first_name"
        )
        search = request.query_params.get("search", "").strip()
        if search:
            rows = rows.filter(
                Q(member__last_name__icontains=search)
                | Q(member__first_name__icontains=search)
                | Q(member__membership_number__icontains=search)
            )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(MemberDividendSerializer(page, many=True).data)
