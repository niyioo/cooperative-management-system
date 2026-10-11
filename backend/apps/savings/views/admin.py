"""/api/v1/admin/savings/ — products, Christmas Savings cycles, accounts and postings."""
import django_filters
from django.db.models import Count, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import OfficerAPIMixin
from apps.audit.services import record
from apps.configuration.models import CooperativeSettings
from apps.accounts.perms import P
from apps.common.fields import MoneyField
from apps.common.serializers import money_to_str
from apps.ledger.choices import TransactionType
from apps.ledger.models import Transaction
from apps.ledger.selectors import SIGNED_AMOUNT, ZERO, with_balance
from apps.ledger.serializers import BatchSerializer, TransactionSerializer

from .. import services, statutory
from ..models import SavingsAccount, SavingsCycle, SavingsProduct
from ..selectors import cycle_grid
from ..serializers import (
    ContributionSerializer,
    DeductionScheduleQuerySerializer,
    MonthlyContributionSerializer,
    PayoutSerializer,
    SavingsAccountCreateSerializer,
    SavingsAccountSerializer,
    SavingsAccountUpdateSerializer,
    SavingsCycleCreateSerializer,
    SavingsCycleSerializer,
    SavingsCycleUpdateSerializer,
    SavingsProductSerializer,
    WithdrawalSerializer,
)

UUID_RE = r"[0-9a-fA-F-]{36}"


class SavingsProductViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SavingsProductSerializer
    queryset = SavingsProduct.objects.all()
    lookup_value_regex = UUID_RE
    filterset_fields = ["kind", "is_active"]
    search_fields = ["name", "code"]
    permission_map = {
        "list": (),  # any officer: needed for posting forms and filters
        "retrieve": (),
        "create": (P.MANAGE_SAVINGS_PRODUCTS,),
        "partial_update": (P.MANAGE_SAVINGS_PRODUCTS,),
    }

    @extend_schema(request=SavingsProductSerializer, responses={201: SavingsProductSerializer})
    def create(self, request):
        serializer = SavingsProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(request.user, **serializer.validated_data)
        return Response(SavingsProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=SavingsProductSerializer, responses={200: SavingsProductSerializer})
    def partial_update(self, request, pk=None):
        product = self.get_object()
        serializer = SavingsProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = services.update_product(request.user, product, **serializer.validated_data)
        return Response(SavingsProductSerializer(product).data)


class SavingsCycleViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SavingsCycleSerializer
    lookup_value_regex = UUID_RE
    filterset_fields = ["product", "year", "status"]
    permission_map = {
        "list": (P.VIEW_SAVINGS,),
        "retrieve": (P.VIEW_SAVINGS,),
        "grid": (P.VIEW_SAVINGS,),
        "create": (P.MANAGE_SAVINGS_CYCLES,),
        "partial_update": (P.MANAGE_SAVINGS_CYCLES,),
        "open": (P.MANAGE_SAVINGS_CYCLES,),
        "close": (P.CLOSE_SAVINGS_CYCLE,),
        "payout": (P.MANAGE_BATCHES, P.POST_SAVINGS_WITHDRAWAL),
    }

    def get_queryset(self):
        saved = (
            Transaction.objects.posted()
            .filter(savings_account__cycle=OuterRef("pk"))
            .exclude(txn_type=TransactionType.SAVINGS_CYCLE_PAYOUT)
            .values("savings_account__cycle")
            .annotate(total=Sum(SIGNED_AMOUNT))
            .values("total")
        )
        return SavingsCycle.objects.select_related("product").annotate(
            account_count=Count("accounts", distinct=True),
            total_saved=Coalesce(Subquery(saved, output_field=MoneyField()), Value(ZERO), output_field=MoneyField()),
        ).order_by("-year", "product__display_order")  # Meta.ordering is dropped on grouped queries

    def _read(self, cycle):
        return SavingsCycleSerializer(self.get_queryset().get(pk=cycle.pk)).data

    @extend_schema(request=SavingsCycleCreateSerializer, responses={201: SavingsCycleSerializer})
    def create(self, request):
        serializer = SavingsCycleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = services.create_cycle(request.user, **serializer.validated_data)
        return Response(self._read(cycle), status=status.HTTP_201_CREATED)

    @extend_schema(request=SavingsCycleUpdateSerializer, responses={200: SavingsCycleSerializer})
    def partial_update(self, request, pk=None):
        serializer = SavingsCycleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cycle = services.update_cycle(request.user, self.get_object(), **serializer.validated_data)
        return Response(self._read(cycle))

    @extend_schema(request=None, responses={200: SavingsCycleSerializer})
    @action(detail=True, methods=["post"])
    def open(self, request, pk=None):
        cycle, opened = services.open_cycle(request.user, self.get_object())
        data = self._read(cycle)
        data["accounts_opened"] = opened
        return Response(data)

    @extend_schema(request=None, responses={200: SavingsCycleSerializer})
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return Response(self._read(services.close_cycle(request.user, self.get_object())))

    @extend_schema(request=PayoutSerializer, responses={201: BatchSerializer})
    @action(detail=True, methods=["post"])
    def payout(self, request, pk=None):
        serializer = PayoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = services.prepare_cycle_payout(request.user, self.get_object(), **serializer.validated_data)
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: OpenApiResponse(description="Members × months contribution grid")})
    @action(detail=True, methods=["get"])
    def grid(self, request, pk=None):
        cycle = self.get_object()
        accounts = cycle.accounts.select_related("member").order_by("member__last_name", "member__first_name")
        search = request.query_params.get("search", "").strip()
        if search:
            accounts = accounts.filter(
                Q(member__last_name__icontains=search)
                | Q(member__first_name__icontains=search)
                | Q(member__membership_number__icontains=search)
            )
        page = self.paginate_queryset(accounts)
        grid = cycle_grid(cycle, page)
        return self.get_paginated_response(money_to_str(grid))


class SavingsAccountFilter(django_filters.FilterSet):
    member = django_filters.UUIDFilter(field_name="member_id")
    product = django_filters.UUIDFilter(field_name="product_id")
    cycle = django_filters.UUIDFilter(field_name="cycle_id")
    status = django_filters.ChoiceFilter(choices=SavingsAccount.Status.choices)

    class Meta:
        model = SavingsAccount
        fields = ["member", "product", "cycle", "status"]


class SavingsAccountViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SavingsAccountSerializer
    filterset_class = SavingsAccountFilter
    lookup_value_regex = UUID_RE
    search_fields = ["account_number", "member__membership_number", "member__last_name", "member__first_name"]
    ordering_fields = ["opened_on", "account_number", "balance"]
    permission_map = {
        "list": (P.VIEW_SAVINGS,),
        "retrieve": (P.VIEW_SAVINGS,),
        "transactions": (P.VIEW_SAVINGS,),
        "create": (P.POST_SAVINGS_CONTRIBUTION,),
        "partial_update": (P.POST_SAVINGS_CONTRIBUTION,),
        "monthly_contribution:get": (P.VIEW_SAVINGS,),
        "monthly_contribution:post": (P.POST_SAVINGS_CONTRIBUTION,),
    }

    def get_queryset(self):
        return with_balance(
            SavingsAccount.objects.select_related("member", "product", "cycle"), "savings_account"
        ).order_by("member__last_name", "product__display_order")

    def _read(self, account):
        return SavingsAccountSerializer(self.get_queryset().get(pk=account.pk)).data

    @extend_schema(request=SavingsAccountCreateSerializer, responses={201: SavingsAccountSerializer})
    def create(self, request):
        serializer = SavingsAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = services.open_account(request.user, **serializer.validated_data)
        return Response(self._read(account), status=status.HTTP_201_CREATED)

    @extend_schema(request=SavingsAccountUpdateSerializer, responses={200: SavingsAccountSerializer})
    def partial_update(self, request, pk=None):
        serializer = SavingsAccountUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        account = services.update_account(request.user, self.get_object(), **serializer.validated_data)
        return Response(self._read(account))

    @extend_schema(responses={200: TransactionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        entries = self.get_object().transactions.select_related("savings_account__product", "savings_account__cycle")
        page = self.paginate_queryset(entries.order_by("-value_date", "-created_at"))
        return self.get_paginated_response(TransactionSerializer(page, many=True).data)


    @extend_schema(
        methods=["GET"], request=None,
        responses={200: OpenApiResponse(description="Monthly amount, scheduled change, arrears and history")},
    )
    @extend_schema(
        methods=["POST"], request=MonthlyContributionSerializer,
        responses={200: OpenApiResponse(description="The updated position")},
    )
    @action(detail=True, methods=["get", "post"], url_path="monthly-contribution")
    def monthly_contribution(self, request, pk=None):
        """The statutory monthly contribution (BR-29). Only for the mandatory regular savings account."""
        account = self.get_object()
        if not statutory.is_statutory(account):
            raise NotFound("This account has no monthly contribution.")
        if request.method == "POST":
            serializer = MonthlyContributionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            statutory.set_monthly_contribution(request.user, account, **serializer.validated_data)
        return Response(money_to_str(statutory.position(account)))


SCHEDULE_PARAMS = [
    OpenApiParameter("period", str, description='Payroll month, e.g. "2026-10". Defaults to this month.'),
    OpenApiParameter("include_arrears", bool, description="Add each member's arrears to the deduction (default true)."),
]


def _schedule(request):
    query = DeductionScheduleQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    period = query.validated_data.get("period") or statutory.this_month()
    return statutory.deduction_schedule(period, include_arrears=query.validated_data["include_arrears"])


class DeductionScheduleView(OfficerAPIMixin, APIView):
    """What payroll should deduct for the statutory monthly contribution (on-screen preview)."""

    permission_map = {"get": (P.VIEW_SAVINGS,)}

    @extend_schema(parameters=SCHEDULE_PARAMS, responses={200: OpenApiResponse(description="Rows and totals")})
    def get(self, request):
        return Response(money_to_str(_schedule(request)))


class DeductionScheduleDownloadView(OfficerAPIMixin, APIView):
    """The schedule as Excel, in the CONTRIBUTIONS batch layout so the same sheet can be uploaded back."""

    permission_map = {"get": (P.POST_SAVINGS_CONTRIBUTION,)}

    @extend_schema(
        parameters=SCHEDULE_PARAMS,
        responses={
            (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiResponse(description="Deduction schedule")
        },
    )
    def get(self, request):
        schedule = _schedule(request)
        content = statutory.schedule_workbook(schedule, CooperativeSettings.load().name)
        record(
            "savings.deduction_schedule_exported",
            actor=request.user,
            metadata={
                "period": schedule["period"],
                "include_arrears": schedule["include_arrears"],
                "members": schedule["totals"]["members"],
                "amount": schedule["totals"]["amount"],
            },
        )
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="emdi-deductions-{schedule["period"]}.xlsx"'
        return response


class ContributionView(OfficerAPIMixin, APIView):
    """Record one contribution (e.g. cash or a transfer outside payroll)."""

    permission_map = {"post": (P.POST_SAVINGS_CONTRIBUTION,)}

    @extend_schema(request=ContributionSerializer, responses={201: TransactionSerializer})
    def post(self, request):
        serializer = ContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.post_contribution(request.user, **serializer.validated_data)
        return Response(TransactionSerializer(entry).data, status=status.HTTP_201_CREATED)


class WithdrawalView(OfficerAPIMixin, APIView):
    """Officer withdrawal, only for products that allow it (none do for EMDI)."""

    permission_map = {"post": (P.POST_SAVINGS_WITHDRAWAL,)}

    @extend_schema(request=WithdrawalSerializer, responses={201: TransactionSerializer})
    def post(self, request):
        serializer = WithdrawalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.post_withdrawal(request.user, **serializer.validated_data)
        return Response(TransactionSerializer(entry).data, status=status.HTTP_201_CREATED)
