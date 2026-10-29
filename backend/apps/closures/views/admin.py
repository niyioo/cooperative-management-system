"""/api/v1/admin/closure-requests/ — review, approve and execute account closures."""
from pathlib import Path

import django_filters
from django.http import FileResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.serializers import money_to_str
from apps.ledger.serializers import BatchSerializer
from apps.savings.serializers import MemberBriefSerializer

from .. import services
from ..models import AccountClosureRequest


class ClosureRequestSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reason_category_label = serializers.CharField(source="get_reason_category_display", read_only=True)
    reviewed_by = serializers.CharField(source="reviewed_by.full_name", default=None, read_only=True)
    decided_by = serializers.CharField(source="decided_by.full_name", default=None, read_only=True)
    closed_by = serializers.CharField(source="closed_by.full_name", default=None, read_only=True)
    has_attachment = serializers.SerializerMethodField()
    settlement_batch = serializers.SerializerMethodField()

    class Meta:
        model = AccountClosureRequest
        fields = ["id", "reference", "member", "reason_category", "reason_category_label", "reason", "additional_information",
                  "status", "status_label", "has_attachment", "reviewed_by", "reviewed_at", "review_notes", "decided_by",
                  "decided_at", "decision_reason", "settlement_statement", "settlement_batch", "closed_by", "closed_at",
                  "withdrawn_at", "created_at"]

    def get_has_attachment(self, obj) -> bool:
        return bool(obj.attachment)

    def get_settlement_batch(self, obj) -> dict | None:
        batch = services.open_settlement_batch(obj)
        return {"id": str(batch.pk), "reference": batch.reference, "status": batch.status} if batch else None


class NotesSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ClosureReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class ExecuteSerializer(serializers.Serializer):
    value_date = serializers.DateField(required=False)


class ClosureFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=AccountClosureRequest.Status.choices)

    class Meta:
        model = AccountClosureRequest
        fields = ["status"]


class ClosureRequestViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ClosureRequestSerializer
    filterset_class = ClosureFilter
    lookup_value_regex = r"[0-9a-fA-F-]{36}"
    search_fields = ["reference", "member__membership_number", "member__last_name", "member__first_name"]
    permission_map = {
        "list": (P.VIEW_CLOSURE_REQUESTS,),
        "retrieve": (P.VIEW_CLOSURE_REQUESTS,),
        "settlement": (P.VIEW_CLOSURE_REQUESTS,),
        "attachment": (P.VIEW_CLOSURE_REQUESTS,),
        "start_review": (P.REVIEW_CLOSURE_REQUEST,),
        "approve": (P.APPROVE_CLOSURE_REQUEST,),
        "reject": (P.APPROVE_CLOSURE_REQUEST,),
        "execute": (P.EXECUTE_ACCOUNT_CLOSURE,),
    }

    def get_queryset(self):
        return AccountClosureRequest.objects.select_related("member", "reviewed_by", "decided_by", "closed_by").order_by("-created_at")

    def _read(self, closure_request):
        return ClosureRequestSerializer(self.get_queryset().get(pk=closure_request.pk)).data

    @extend_schema(responses={200: OpenApiResponse(description="Live settlement figures from current balances")})
    @action(detail=True, methods=["get"])
    def settlement(self, request, pk=None):
        return Response(money_to_str(services.settlement_statement(self.get_object().member)))

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiResponse(description="The member's attachment")})
    @action(detail=True, methods=["get"])
    def attachment(self, request, pk=None):
        closure_request = self.get_object()
        if not closure_request.attachment:
            raise NotFound("No attachment.")
        record("closure.attachment_downloaded", actor=request.user, obj=closure_request)
        return FileResponse(closure_request.attachment.open("rb"), as_attachment=True,
                            filename=f"{closure_request.reference}{Path(closure_request.attachment.name).suffix}")

    @extend_schema(request=NotesSerializer, responses={200: ClosureRequestSerializer})
    @action(detail=True, methods=["post"], url_path="start-review")
    def start_review(self, request, pk=None):
        serializer = NotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._read(services.start_review(request.user, self.get_object(), **serializer.validated_data)))

    @extend_schema(request=NotesSerializer, responses={200: ClosureRequestSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = NotesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._read(services.approve_request(request.user, self.get_object(), **serializer.validated_data)))

    @extend_schema(request=ClosureReasonSerializer, responses={200: ClosureRequestSerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = ClosureReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self._read(services.reject_request(request.user, self.get_object(), **serializer.validated_data)))

    @extend_schema(request=ExecuteSerializer, responses={200: OpenApiResponse(description="The request, plus the settlement batch if one was needed")})
    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        serializer = ExecuteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closure_request, batch = services.execute(request.user, self.get_object(), **serializer.validated_data)
        return Response({"request": self._read(closure_request), "batch": BatchSerializer(batch).data if batch else None})
