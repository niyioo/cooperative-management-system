"""/api/v1/me/ loans: products with personal eligibility, applications, and the member's own loans."""
from pathlib import Path

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin, member_scoped
from apps.common.exceptions import DomainError
from apps.common.serializers import money_to_str, validate_model_field
from apps.ledger.selectors import ZERO, with_balance
from apps.common.parsers import UPLOAD_PARSERS

from .. import services
from ..eligibility import evaluate
from ..models import Loan, LoanApplication, LoanApplicationDocument, LoanGuarantor, LoanProduct
from ..selectors import arrears_from_rows, loan_schedule, next_instalment
from ..serializers import (
    MONEY,
    POSITIVE,
    ApplicationDocumentSerializer,
    LoanRepaymentOutSerializer,
    LoanSerializer,
    QuoteQuerySerializer,
    schedule_preview,
)

UUID_RE = r"[0-9a-fA-F-]{36}"
APP = LoanApplication.Status
EDITABLE = [APP.DRAFT, APP.RETURNED]
AWAITING_GUARANTORS = [APP.SUBMITTED, APP.UNDER_REVIEW]
CANCELLABLE = [APP.DRAFT, APP.SUBMITTED, APP.UNDER_REVIEW, APP.RETURNED, APP.APPROVED]


class MyLoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ["id", "name", "code", "description", "interest_rate", "interest_rate_basis", "interest_method",
                  "interest_collection", "min_amount", "max_amount", "min_term_months", "max_term_months",
                  "allowed_terms", "guarantors_required", "required_documents"]


class MyLoanProductViewSet(MemberAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = MyLoanProductSerializer
    lookup_value_regex = UUID_RE
    pagination_class = None

    def get_queryset(self):
        return LoanProduct.objects.filter(is_active=True).order_by("name")

    def _with_eligibility(self, product):
        data = MyLoanProductSerializer(product).data
        data["eligibility"] = money_to_str(evaluate(self.member, product))
        return data

    @extend_schema(responses={200: OpenApiResponse(description="Active loan products with this member's eligibility")})
    def list(self, request):
        return Response([self._with_eligibility(p) for p in self.get_queryset()])

    @extend_schema(responses={200: OpenApiResponse(description="Product with this member's eligibility")})
    def retrieve(self, request, pk=None):
        return Response(self._with_eligibility(self.get_object()))

    @extend_schema(parameters=[QuoteQuerySerializer], responses={200: OpenApiResponse(description="Repayment schedule preview")})
    @action(detail=True, methods=["get"])
    def quote(self, request, pk=None):
        product = self.get_object()
        query = QuoteQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        amount, term = query.validated_data["amount"], query.validated_data["term_months"]
        data = schedule_preview(product, amount, term)
        data["eligibility"] = money_to_str(evaluate(self.member, product, amount=amount, term_months=term))
        return Response(data)


class MyGuarantorSerializer(serializers.ModelSerializer):
    membership_number = serializers.CharField(source="guarantor.membership_number", read_only=True)
    full_name = serializers.CharField(source="guarantor.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LoanGuarantor
        fields = ["id", "membership_number", "full_name", "amount_guaranteed", "status", "status_label",
                  "requested_at", "responded_at", "decline_reason"]


class MyApplicationSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    guarantors = MyGuarantorSerializer(many=True, read_only=True)
    guarantors_required = serializers.IntegerField(source="product.guarantors_required", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    documents = ApplicationDocumentSerializer(many=True, read_only=True)
    loan = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = LoanApplication
        # Officers' internal review notes and reviewer names are deliberately not exposed.
        fields = ["id", "reference", "product", "product_name", "amount_requested", "term_months", "purpose",
                  "status", "status_label", "submitted_at", "info_request_message", "approved_amount",
                  "approved_term_months", "decided_at", "decision_reason", "cancelled_at", "created_at",
                  "documents", "guarantors", "guarantors_required", "loan", "quote", "can_edit", "can_cancel"]

    def get_loan(self, obj) -> dict | None:
        loan = obj.loans.exclude(status=Loan.Status.CANCELLED).first()
        return {"id": str(loan.pk), "reference": loan.reference, "status": loan.status} if loan else None

    def get_quote(self, obj) -> dict:
        return schedule_preview(obj.product, obj.approved_amount or obj.amount_requested, obj.approved_term_months or obj.term_months)

    def get_can_edit(self, obj) -> bool:
        return obj.status in EDITABLE

    def get_can_cancel(self, obj) -> bool:
        return obj.status in CANCELLABLE and not obj.loans.filter(status=Loan.Status.PENDING_DISBURSEMENT).exists()


class MyApplicationWriteSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=LoanProduct.objects.filter(is_active=True))
    amount_requested = serializers.DecimalField(**POSITIVE)
    term_months = serializers.IntegerField(min_value=1)
    purpose = serializers.CharField(max_length=2000)


class DocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=150)
    file = serializers.FileField()

    def validate_file(self, value):
        return validate_model_field(LoanApplicationDocument, "file", value)


class GuarantorInSerializer(serializers.Serializer):
    membership_number = serializers.CharField(max_length=30)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class MyLoanApplicationViewSet(
    MemberAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = MyApplicationSerializer
    lookup_value_regex = UUID_RE

    @member_scoped(LoanApplication)
    def get_queryset(self):
        # Scoped to the member: another member's application is simply "not found".
        return (
            LoanApplication.objects.filter(member=self.member)
            .select_related("product")
            .prefetch_related("documents__uploaded_by", "loans", "guarantors__guarantor")
            .order_by("-created_at")
        )

    def _read(self, application):
        return MyApplicationSerializer(self.get_queryset().get(pk=application.pk)).data

    @extend_schema(request=MyApplicationWriteSerializer, responses={201: MyApplicationSerializer}, summary="Start a draft application")
    def create(self, request):
        serializer = MyApplicationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = services.create_application(request.user, member=self.member, **serializer.validated_data)
        return Response(self._read(application), status=status.HTTP_201_CREATED)

    @extend_schema(request=MyApplicationWriteSerializer, responses={200: MyApplicationSerializer})
    def partial_update(self, request, pk=None):
        serializer = MyApplicationWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        application = services.update_application(request.user, self.get_object(), **serializer.validated_data)
        return Response(self._read(application))

    @extend_schema(request=None, responses={200: MyApplicationSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return Response(self._read(services.submit_application(request.user, self.get_object())))

    @extend_schema(request=CancelSerializer, responses={200: MyApplicationSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._read(services.cancel_application(request.user, self.get_object(), **serializer.validated_data)))

    @extend_schema(methods=["get"], responses={200: ApplicationDocumentSerializer(many=True)})
    @extend_schema(methods=["post"], request={"multipart/form-data": DocumentUploadSerializer}, responses={201: ApplicationDocumentSerializer})
    @action(detail=True, methods=["get", "post"], parser_classes=UPLOAD_PARSERS)
    def documents(self, request, pk=None):
        application = self.get_object()
        if request.method == "GET":
            return Response(ApplicationDocumentSerializer(application.documents.all(), many=True).data)
        if application.status not in EDITABLE:
            raise DomainError("Documents can only be added while the application is a draft or returned to you.", code="invalid_transition")
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = LoanApplicationDocument.objects.create(application=application, uploaded_by=request.user, **serializer.validated_data)
        return Response(ApplicationDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiResponse(description="The file")})
    @action(detail=True, methods=["get"], url_path=rf"documents/(?P<document_id>{UUID_RE})/download")
    def document_download(self, request, pk=None, document_id=None):
        application = self.get_object()
        document = get_object_or_404(LoanApplicationDocument, pk=document_id, application=application)
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=f"{document.title}{Path(document.file.name).suffix}")

    @extend_schema(request=GuarantorInSerializer, responses={201: MyApplicationSerializer},
                   summary="Add a guarantor by membership number (draft or returned applications)")
    @action(detail=True, methods=["post"])
    def guarantors(self, request, pk=None):
        serializer = GuarantorInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.get_object()
        services.add_guarantor(request.user, application, serializer.validated_data["membership_number"])
        return Response(self._read(application), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: MyApplicationSerializer})
    @action(detail=True, methods=["delete"], url_path=rf"guarantors/(?P<guarantor_id>{UUID_RE})")
    def guarantor_remove(self, request, pk=None, guarantor_id=None):
        application = self.get_object()
        guarantee = get_object_or_404(LoanGuarantor, pk=guarantor_id, application=application)
        services.remove_guarantor(request.user, application, guarantee)
        return Response(self._read(application))


class GuarantorLookupView(MemberAPIMixin, APIView):
    """
    Confirm who a membership number belongs to before adding them as guarantor.
    Returns only the name, only for active members, and is rate-limited.
    """

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "guarantor_lookup"

    @extend_schema(parameters=[GuarantorInSerializer], responses={200: OpenApiResponse(description="{membership_number, full_name}")})
    def get(self, request):
        query = GuarantorInSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        member = services.find_guarantor(self.member, query.validated_data["membership_number"])
        return Response({"membership_number": member.membership_number, "full_name": member.full_name})


class GuaranteeRequestSerializer(serializers.ModelSerializer):
    application_id = serializers.UUIDField(source="application.id", read_only=True)
    application_reference = serializers.CharField(source="application.reference", read_only=True)
    applicant = serializers.SerializerMethodField()
    product_name = serializers.CharField(source="application.product.name", read_only=True)
    amount_requested = serializers.DecimalField(source="application.amount_requested", read_only=True, **MONEY)
    term_months = serializers.IntegerField(source="application.term_months", read_only=True)
    purpose = serializers.CharField(source="application.purpose", read_only=True)
    application_status = serializers.CharField(source="application.status", read_only=True)
    application_status_label = serializers.CharField(source="application.get_status_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    can_respond = serializers.SerializerMethodField()

    class Meta:
        model = LoanGuarantor
        fields = ["id", "application_id", "application_reference", "applicant", "product_name", "amount_requested", "term_months",
                  "purpose", "amount_guaranteed", "status", "status_label", "application_status", "application_status_label",
                  "requested_at", "responded_at", "decline_reason", "can_respond"]

    def get_applicant(self, obj) -> dict:
        member = obj.application.member
        return {"full_name": member.full_name, "membership_number": member.membership_number}

    def get_can_respond(self, obj) -> bool:
        return obj.status == LoanGuarantor.Status.PENDING and obj.application.status in AWAITING_GUARANTORS


class DeclineSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class MyGuaranteeRequestViewSet(MemberAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Requests from other members to stand as their guarantor. ?awaiting=true lists only those needing an answer."""

    serializer_class = GuaranteeRequestSerializer
    lookup_value_regex = UUID_RE
    filter_backends = []

    @member_scoped(LoanGuarantor)
    def get_queryset(self):
        qs = (
            LoanGuarantor.objects.filter(guarantor=self.member, requested_at__isnull=False)
            .select_related("application__member", "application__product")
            .order_by("-requested_at")
        )
        if self.request.query_params.get("awaiting") in ("1", "true"):
            qs = qs.filter(status=LoanGuarantor.Status.PENDING, application__status__in=AWAITING_GUARANTORS)
        return qs

    @extend_schema(request=None, responses={200: GuaranteeRequestSerializer})
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        guarantee = services.respond_to_guarantee(request.user, self.get_object(), accept=True)
        return Response(GuaranteeRequestSerializer(LoanGuarantor.objects.get(pk=guarantee.pk)).data)

    @extend_schema(request=DeclineSerializer, responses={200: GuaranteeRequestSerializer})
    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        serializer = DeclineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guarantee = services.respond_to_guarantee(request.user, self.get_object(), accept=False, **serializer.validated_data)
        return Response(GuaranteeRequestSerializer(LoanGuarantor.objects.get(pk=guarantee.pk)).data)


class MyLoanViewSet(MemberAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LoanSerializer
    lookup_value_regex = UUID_RE

    @member_scoped(Loan)
    def get_queryset(self):
        return with_balance(
            Loan.objects.filter(member=self.member).exclude(status=Loan.Status.CANCELLED).select_related("member", "product"),
            "loan",
        ).order_by("-disbursed_on")

    @extend_schema(responses={200: OpenApiResponse(description="Loan with schedule, arrears and next instalment")})
    def retrieve(self, request, pk=None):
        loan = self.get_object()
        rows = loan_schedule(loan)
        data = LoanSerializer(loan).data
        data.update(money_to_str({
            "schedule": rows,
            "arrears": arrears_from_rows(rows, timezone.localdate()),
            "next_instalment": next_instalment(rows),
            "amount_repaid": sum((r["paid"] for r in rows), ZERO),
        }))
        return Response(data)

    @extend_schema(responses={200: LoanRepaymentOutSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def repayments(self, request, pk=None):
        repayments = self.get_object().repayments.select_related("transaction").order_by("-transaction__value_date", "-created_at")
        page = self.paginate_queryset(repayments)
        return self.get_paginated_response(LoanRepaymentOutSerializer(page, many=True).data)
