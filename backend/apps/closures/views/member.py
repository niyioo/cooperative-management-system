"""/api/v1/me/closure-requests/ — apply to close one's own account (BR-11)."""
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import MemberAPIMixin, member_scoped
from apps.common.serializers import validate_model_field
from apps.common.parsers import UPLOAD_PARSERS

from .. import services
from ..models import AccountClosureRequest


class MyClosureRequestSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    reason_category_label = serializers.CharField(source="get_reason_category_display", read_only=True)
    can_withdraw = serializers.SerializerMethodField()

    class Meta:
        model = AccountClosureRequest
        # Officers' internal review notes are deliberately not exposed.
        fields = ["id", "reference", "reason_category", "reason_category_label", "reason", "additional_information",
                  "status", "status_label", "decision_reason", "decided_at", "closed_at", "withdrawn_at",
                  "created_at", "can_withdraw"]

    def get_can_withdraw(self, obj) -> bool:
        return obj.status == AccountClosureRequest.Status.SUBMITTED


class ClosureRequestCreateSerializer(serializers.Serializer):
    reason_category = serializers.ChoiceField(choices=AccountClosureRequest.ReasonCategory.choices)
    reason = serializers.CharField(max_length=2000)
    additional_information = serializers.CharField(max_length=4000, required=False, allow_blank=True, default="")
    confirmed = serializers.BooleanField()
    attachment = serializers.FileField(required=False, allow_null=True)

    def validate_attachment(self, value):
        return validate_model_field(AccountClosureRequest, "attachment", value) if value else value


class MyClosureRequestViewSet(MemberAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    parser_classes = UPLOAD_PARSERS  # create receives a file
    serializer_class = MyClosureRequestSerializer
    lookup_value_regex = r"[0-9a-fA-F-]{36}"

    @member_scoped(AccountClosureRequest)
    def get_queryset(self):
        return AccountClosureRequest.objects.filter(member=self.member).order_by("-created_at")

    @extend_schema(request={"multipart/form-data": ClosureRequestCreateSerializer}, responses={201: MyClosureRequestSerializer})
    def create(self, request):
        serializer = ClosureRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closure = services.submit_request(self.member, **serializer.validated_data)
        return Response(MyClosureRequestSerializer(closure).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: MyClosureRequestSerializer})
    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        return Response(MyClosureRequestSerializer(services.withdraw_request(self.member, self.get_object())).data)
