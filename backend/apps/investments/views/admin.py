"""/api/v1/admin/investments/ — schemes, member investment accounts and scheme returns."""
import django_filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.ledger.selectors import with_balance
from apps.ledger.serializers import TransactionSerializer

from .. import services
from ..models import InvestmentAccount, InvestmentProduct, InvestmentReturn
from ..serializers import (
    InvestmentAccountCreateSerializer,
    InvestmentAccountSerializer,
    InvestmentContributionSerializer,
    InvestmentProductSerializer,
    InvestmentReturnSerializer,
    LiquidationSerializer,
)

UUID_RE = r"[0-9a-fA-F-]{36}"


class InvestmentProductViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = InvestmentProductSerializer
    queryset = InvestmentProduct.objects.all()
    lookup_value_regex = UUID_RE
    filterset_fields = ["is_active", "dividend_eligible"]
    search_fields = ["name", "code"]
    permission_map = {
        "list": (),
        "retrieve": (),
        "create": (P.MANAGE_INVESTMENT_PRODUCTS,),
        "partial_update": (P.MANAGE_INVESTMENT_PRODUCTS,),
    }

    @extend_schema(request=InvestmentProductSerializer, responses={201: InvestmentProductSerializer})
    def create(self, request):
        serializer = InvestmentProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(request.user, **serializer.validated_data)
        return Response(InvestmentProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=InvestmentProductSerializer, responses={200: InvestmentProductSerializer})
    def partial_update(self, request, pk=None):
        product = self.get_object()
        serializer = InvestmentProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(InvestmentProductSerializer(services.update_product(request.user, product, **serializer.validated_data)).data)


class InvestmentAccountFilter(django_filters.FilterSet):
    member = django_filters.UUIDFilter(field_name="member_id")
    product = django_filters.UUIDFilter(field_name="product_id")
    status = django_filters.ChoiceFilter(choices=InvestmentAccount.Status.choices)

    class Meta:
        model = InvestmentAccount
        fields = ["member", "product", "status"]


class InvestmentAccountViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = InvestmentAccountSerializer
    filterset_class = InvestmentAccountFilter
    lookup_value_regex = UUID_RE
    search_fields = ["account_number", "member__membership_number", "member__last_name", "member__first_name"]
    ordering_fields = ["opened_on", "balance"]
    permission_map = {
        "list": (P.VIEW_INVESTMENTS,),
        "retrieve": (P.VIEW_INVESTMENTS,),
        "transactions": (P.VIEW_INVESTMENTS,),
        "create": (P.MANAGE_INVESTMENT_ACCOUNTS,),
        "contributions": (P.POST_INVESTMENT_TRANSACTION,),
        "liquidations": (P.POST_INVESTMENT_TRANSACTION,),
    }

    def get_queryset(self):
        return with_balance(InvestmentAccount.objects.select_related("member", "product"), "investment_account").order_by(
            "member__last_name", "product__name"
        )

    def _read(self, account):
        return InvestmentAccountSerializer(self.get_queryset().get(pk=account.pk)).data

    @extend_schema(request=InvestmentAccountCreateSerializer, responses={201: InvestmentAccountSerializer})
    def create(self, request):
        serializer = InvestmentAccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = services.open_account(request.user, **serializer.validated_data)
        return Response(self._read(account), status=status.HTTP_201_CREATED)

    @extend_schema(request=InvestmentContributionSerializer, responses={201: TransactionSerializer})
    @action(detail=True, methods=["post"])
    def contributions(self, request, pk=None):
        serializer = InvestmentContributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.post_contribution(request.user, account=self.get_object(), **serializer.validated_data)
        return Response(TransactionSerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=LiquidationSerializer, responses={201: TransactionSerializer})
    @action(detail=True, methods=["post"])
    def liquidations(self, request, pk=None):
        serializer = LiquidationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.liquidate(request.user, account=self.get_object(), **serializer.validated_data)
        return Response(TransactionSerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: TransactionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        entries = self.get_object().transactions.select_related("investment_account__product").order_by("-value_date", "-created_at")
        page = self.paginate_queryset(entries)
        return self.get_paginated_response(TransactionSerializer(page, many=True).data)


class InvestmentReturnViewSet(OfficerAPIMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = InvestmentReturnSerializer
    filterset_fields = ["product", "financial_year"]
    permission_map = {"list": (P.VIEW_INVESTMENTS,), "create": (P.POST_INVESTMENT_TRANSACTION,)}

    def get_queryset(self):
        return InvestmentReturn.objects.select_related("product", "recorded_by")

    @extend_schema(request=InvestmentReturnSerializer, responses={201: InvestmentReturnSerializer})
    def create(self, request):
        serializer = InvestmentReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.record_return(request.user, **serializer.validated_data)
        return Response(InvestmentReturnSerializer(entry).data, status=status.HTTP_201_CREATED)
