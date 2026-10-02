"""/api/v1/admin/loans/ — products, applications, loans, repayments and overdue tracking."""
from pathlib import Path

import django_filters
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.serializers import money_to_str
from apps.ledger.selectors import with_balance
from apps.ledger.serializers import TransactionSerializer

from .. import services
from ..eligibility import evaluate
from ..models import Loan, LoanApplication, LoanApplicationDocument, LoanProduct
from ..selectors import arrears_from_rows, loan_schedule, next_instalment, overdue_loans
from ..serializers import (
    ApplicationOnBehalfSerializer,
    ApproveSerializer,
    DisburseSerializer,
    EligibilityQuerySerializer,
    LoanApplicationDetailSerializer,
    LoanApplicationListSerializer,
    LoanProductSerializer,
    LoanRepaymentOutSerializer,
    LoanSerializer,
    MarkDefaultSerializer,
    QuoteQuerySerializer,
    RejectSerializer,
    RepaymentInSerializer,
    ReturnSerializer,
    ReviewSerializer,
    schedule_preview,
)

UUID_RE = r"[0-9a-fA-F-]{36}"


class LoanProductViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LoanProductSerializer
    queryset = LoanProduct.objects.all()
    lookup_value_regex = UUID_RE
    filterset_fields = ["is_active"]
    search_fields = ["name", "code"]
    permission_map = {
        "list": (),
        "retrieve": (),
        "quote": (),
        "create": (P.MANAGE_LOAN_PRODUCTS,),
        "partial_update": (P.MANAGE_LOAN_PRODUCTS,),
    }

    @extend_schema(request=LoanProductSerializer, responses={201: LoanProductSerializer})
    def create(self, request):
        serializer = LoanProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.create_product(request.user, **serializer.validated_data)
        return Response(LoanProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=LoanProductSerializer, responses={200: LoanProductSerializer})
    def partial_update(self, request, pk=None):
        product = self.get_object()
        serializer = LoanProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        product = services.update_product(request.user, product, **serializer.validated_data)
        return Response(LoanProductSerializer(product).data)

    @extend_schema(parameters=[QuoteQuerySerializer], responses={200: OpenApiResponse(description="Repayment schedule preview")})
    @action(detail=True, methods=["get"])
    def quote(self, request, pk=None):
        query = QuoteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(schedule_preview(self.get_object(), query.validated_data["amount"], query.validated_data["term_months"]))


class EligibilityView(OfficerAPIMixin, APIView):
    permission_map = {"get": (P.VIEW_LOANS,)}

    @extend_schema(parameters=[EligibilityQuerySerializer], responses={200: OpenApiResponse(description="Eligibility checks")})
    def get(self, request):
        query = EligibilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        result = evaluate(data["member"], data["product"], amount=data.get("amount"), term_months=data.get("term_months"))
        return Response(money_to_str(result))


class ApplicationFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=LoanApplication.Status.choices)
    member = django_filters.UUIDFilter(field_name="member_id")
    product = django_filters.UUIDFilter(field_name="product_id")
    submitted_from = django_filters.DateFilter(field_name="submitted_at", lookup_expr="date__gte")
    submitted_to = django_filters.DateFilter(field_name="submitted_at", lookup_expr="date__lte")

    class Meta:
        model = LoanApplication
        fields = ["status", "member", "product"]


def _application_action(name, serializer_class, service, description, url_path=None):
    """POST /applications/{id}/<name>/ calling services.<service>(actor, application, **data)."""

    def handler(self, request, pk=None):
        serializer = serializer_class(data=request.data) if serializer_class else None
        if serializer is not None:
            serializer.is_valid(raise_exception=True)
        getattr(services, service)(request.user, self.get_object(), **(serializer.validated_data if serializer else {}))
        return Response(LoanApplicationDetailSerializer(self.get_queryset().get(pk=pk)).data)

    handler.__name__ = name
    handler = action(detail=True, methods=["post"], url_path=url_path or name.replace("_", "-"), url_name=name)(handler)
    return extend_schema(request=serializer_class, responses={200: LoanApplicationDetailSerializer}, summary=description)(handler)


class LoanApplicationViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    filterset_class = ApplicationFilter
    lookup_value_regex = UUID_RE
    search_fields = ["reference", "member__membership_number", "member__last_name", "member__first_name"]
    ordering_fields = ["submitted_at", "created_at", "amount_requested"]
    permission_map = {
        "list": (P.VIEW_LOANS,),
        "retrieve": (P.VIEW_LOANS,),
        "eligibility": (P.VIEW_LOANS,),
        "document_download": (P.VIEW_LOANS,),
        "create": (P.REVIEW_LOAN_APPLICATION,),
        "start_review": (P.REVIEW_LOAN_APPLICATION,),
        "return_to_member": (P.REVIEW_LOAN_APPLICATION,),
        "approve": (P.APPROVE_LOAN_APPLICATION,),
        "reject": (P.APPROVE_LOAN_APPLICATION,),
        "disburse": (P.DISBURSE_LOAN,),
    }

    def get_queryset(self):
        return LoanApplication.objects.select_related(
            "member", "product", "reviewed_by", "decided_by"
        ).prefetch_related("documents__uploaded_by", "guarantors__guarantor", "loans")

    def get_serializer_class(self):
        return LoanApplicationListSerializer if self.action == "list" else LoanApplicationDetailSerializer

    @extend_schema(request=ApplicationOnBehalfSerializer, responses={201: LoanApplicationDetailSerializer},
                   summary="Record a paper application on a member's behalf (submitted immediately)")
    def create(self, request):
        serializer = ApplicationOnBehalfSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        guarantors = data.pop("guarantors")
        with transaction.atomic():
            application = services.create_application(request.user, **data)
            for membership_number in guarantors:
                services.add_guarantor(request.user, application, membership_number)
            services.submit_application(request.user, application)
        return Response(LoanApplicationDetailSerializer(self.get_queryset().get(pk=application.pk)).data, status=status.HTTP_201_CREATED)

    start_review = _application_action("start_review", ReviewSerializer, "start_review", "Take the application under review")
    return_to_member = _application_action("return_to_member", ReturnSerializer, "return_application",
                                           "Return to the member for more information", url_path="return")
    approve = _application_action("approve", ApproveSerializer, "approve_application", "Approve, optionally adjusting amount or term")
    reject = _application_action("reject", RejectSerializer, "reject_application", "Reject with a reason shown to the member")

    @extend_schema(request=DisburseSerializer, responses={200: LoanSerializer})
    @action(detail=True, methods=["post"])
    def disburse(self, request, pk=None):
        serializer = DisburseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = services.disburse(request.user, self.get_object(), **serializer.validated_data)
        return Response(LoanSerializer(with_balance(Loan.objects.select_related("member", "product"), "loan").get(pk=loan.pk)).data)

    @extend_schema(responses={200: OpenApiResponse(description="Eligibility checks against the requested (or approved) terms")})
    @action(detail=True, methods=["get"])
    def eligibility(self, request, pk=None):
        application = self.get_object()
        result = evaluate(
            application.member,
            application.product,
            amount=application.approved_amount or application.amount_requested,
            term_months=application.approved_term_months or application.term_months,
            exclude_application=application,
        )
        return Response(money_to_str(result))

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiResponse(description="The file")})
    @action(detail=True, methods=["get"], url_path=rf"documents/(?P<document_id>{UUID_RE})/download")
    def document_download(self, request, pk=None, document_id=None):
        application = self.get_object()
        document = get_object_or_404(LoanApplicationDocument, pk=document_id, application=application)
        record("loan.document_downloaded", actor=request.user, obj=application, metadata={"document_id": str(document.pk)})
        return FileResponse(
            document.file.open("rb"), as_attachment=True, filename=f"{application.reference}-{document.title}{Path(document.file.name).suffix}"
        )


class LoanFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=Loan.Status.choices)
    member = django_filters.UUIDFilter(field_name="member_id")
    product = django_filters.UUIDFilter(field_name="product_id")
    disbursed_from = django_filters.DateFilter(field_name="disbursed_on", lookup_expr="gte")
    disbursed_to = django_filters.DateFilter(field_name="disbursed_on", lookup_expr="lte")

    class Meta:
        model = Loan
        fields = ["status", "member", "product"]


class LoanViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LoanSerializer
    filterset_class = LoanFilter
    lookup_value_regex = UUID_RE
    search_fields = ["reference", "member__membership_number", "member__last_name", "member__first_name"]
    ordering_fields = ["disbursed_on", "maturity_date", "principal"]
    permission_map = {
        "list": (P.VIEW_LOANS,),
        "retrieve": (P.VIEW_LOANS,),
        "overdue": (P.VIEW_LOANS,),
        "transactions": (P.VIEW_LOANS,),
        "repayments:get": (P.VIEW_LOANS,),
        "repayments:post": (P.RECORD_LOAN_REPAYMENT,),
        "mark_default": (P.MARK_LOAN_DEFAULT,),
    }

    def get_queryset(self):
        return with_balance(Loan.objects.select_related("member", "product", "application"), "loan")

    @extend_schema(responses={200: OpenApiResponse(description="Loan with schedule, arrears and next instalment")})
    def retrieve(self, request, pk=None):
        loan = self.get_object()
        rows = loan_schedule(loan)
        data = LoanSerializer(loan).data
        data.update(
            money_to_str(
                {
                    "application_reference": loan.application.reference if loan.application_id else None,
                    "schedule": rows,
                    "arrears": arrears_from_rows(rows, timezone.localdate()),
                    "next_instalment": next_instalment(rows),
                }
            )
        )
        return Response(data)

    @extend_schema(methods=["get"], responses={200: LoanRepaymentOutSerializer(many=True)})
    @extend_schema(methods=["post"], request=RepaymentInSerializer, responses={201: TransactionSerializer})
    @action(detail=True, methods=["get", "post"])
    def repayments(self, request, pk=None):
        loan = self.get_object()
        if request.method == "GET":
            repayments = loan.repayments.select_related("transaction").order_by("-transaction__value_date", "-created_at")
            page = self.paginate_queryset(repayments)
            return self.get_paginated_response(LoanRepaymentOutSerializer(page, many=True).data)
        serializer = RepaymentInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.record_repayment(request.user, loan, **serializer.validated_data)
        return Response(TransactionSerializer(entry).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: TransactionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        entries = self.get_object().transactions.select_related("loan").order_by("-value_date", "-created_at")
        page = self.paginate_queryset(entries)
        return self.get_paginated_response(TransactionSerializer(page, many=True).data)

    @extend_schema(request=MarkDefaultSerializer, responses={200: LoanSerializer})
    @action(detail=True, methods=["post"], url_path="mark-default")
    def mark_default(self, request, pk=None):
        serializer = MarkDefaultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.mark_default(request.user, self.get_object(), **serializer.validated_data)
        return Response(LoanSerializer(self.get_queryset().get(pk=pk)).data)

    @extend_schema(responses={200: OpenApiResponse(description="Running loans with overdue instalments, worst first")})
    @action(detail=False, methods=["get"])
    def overdue(self, request):
        rows = overdue_loans()
        page = self.paginate_queryset(rows)
        data = [
            {
                "id": str(r["loan"].pk),
                "reference": r["loan"].reference,
                "member": {
                    "id": str(r["loan"].member_id),
                    "membership_number": r["loan"].member.membership_number,
                    "full_name": r["loan"].member.full_name,
                    "phone": r["loan"].member.phone,
                },
                "product_name": r["loan"].product.name,
                "status": r["loan"].status,
                "outstanding": r["outstanding"],
                "arrears": r["arrears"],
            }
            for r in page
        ]
        return self.get_paginated_response(money_to_str(data))
