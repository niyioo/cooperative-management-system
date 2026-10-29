"""/api/v1/admin/audit-logs/ — the read-only audit trail."""
import django_filters
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P

from ..models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    object_type = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "actor", "actor_repr", "action", "object_type", "object_id", "object_repr",
                  "changes", "metadata", "ip_address", "user_agent", "request_id"]

    def get_object_type(self, obj) -> str | None:
        return f"{obj.object_type.app_label}.{obj.object_type.model}" if obj.object_type_id else None


class AuditLogFilter(django_filters.FilterSet):
    actor = django_filters.UUIDFilter(field_name="actor_id")
    action = django_filters.CharFilter(method="filter_action", help_text='Exact action, or a prefix ending in "." (e.g. "loan.")')
    object_type = django_filters.CharFilter(method="filter_object_type", help_text='e.g. "members.member"')
    object_id = django_filters.CharFilter()
    ip_address = django_filters.CharFilter()
    date_from = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["actor", "action", "object_type", "object_id", "ip_address"]

    def filter_action(self, queryset, name, value):
        return queryset.filter(action__startswith=value) if value.endswith(".") else queryset.filter(action=value)

    def filter_object_type(self, queryset, name, value):
        app_label, _, model = value.partition(".")
        return queryset.filter(object_type__app_label=app_label, object_type__model=model)


class AuditLogViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    search_fields = ["actor_repr", "action", "object_repr", "object_id"]
    ordering_fields = ["timestamp", "id"]
    permission_map = {"*": (P.VIEW_AUDIT_LOG,)}

    def get_queryset(self):
        return AuditLog.objects.select_related("object_type").order_by("-id")

    @extend_schema(responses={200: serializers.ListSerializer(child=serializers.CharField())})
    @action(detail=False, methods=["get"])
    def actions(self, request):
        """Distinct action names, for the filter drop-down."""
        prefix = request.query_params.get("prefix", "")
        names = AuditLog.objects.filter(Q(action__startswith=prefix)).order_by("action").values_list("action", flat=True).distinct()
        return Response(list(names))
