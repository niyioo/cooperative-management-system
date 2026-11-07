"""/api/v1/admin/announcements/ and /api/v1/admin/messages/ (officer side of notifications)."""
import re

import django_filters
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.configuration.models import Department
from apps.members.models import Member

from .. import services
from ..models import Announcement, Broadcast


class AnnouncementAdminSerializer(serializers.ModelSerializer):
    audience_label = serializers.CharField(source="get_audience_display", read_only=True)
    created_by = serializers.CharField(source="created_by.full_name", read_only=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "audience", "audience_label", "is_important", "publish_at", "expires_at",
                  "state", "created_by", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
        extra_kwargs = {"publish_at": {"required": False}}

    def get_state(self, obj) -> str:
        now = timezone.now()
        if obj.publish_at > now:
            return "SCHEDULED"
        if obj.expires_at and obj.expires_at <= now:
            return "ENDED"
        return "LIVE"


class AnnouncementFilter(django_filters.FilterSet):
    state = django_filters.ChoiceFilter(choices=[("LIVE", "Live"), ("SCHEDULED", "Scheduled"), ("ENDED", "Ended")], method="filter_state")
    audience = django_filters.ChoiceFilter(choices=Announcement.Audience.choices)

    class Meta:
        model = Announcement
        fields = ["audience"]

    def filter_state(self, queryset, name, value):
        now = timezone.now()
        if value == "SCHEDULED":
            return queryset.filter(publish_at__gt=now)
        if value == "ENDED":
            return queryset.filter(expires_at__lte=now)
        return queryset.filter(publish_at__lte=now).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


class AnnouncementViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                          mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = AnnouncementAdminSerializer
    filterset_class = AnnouncementFilter
    search_fields = ["title", "body"]
    http_method_names = ["get", "post", "patch"]
    permission_map = {"*": (P.MANAGE_ANNOUNCEMENTS,)}

    def get_queryset(self):
        return Announcement.objects.select_related("created_by").order_by("-publish_at")

    def perform_create(self, serializer):
        serializer.instance = services.create_announcement(self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_announcement(self.request.user, serializer.instance, **serializer.validated_data)

    @extend_schema(request=None, responses={200: AnnouncementAdminSerializer})
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        return Response(AnnouncementAdminSerializer(services.end_announcement(request.user, self.get_object())).data)


class BroadcastSerializer(serializers.ModelSerializer):
    audience_label = serializers.CharField(source="get_audience_display", read_only=True)
    department_name = serializers.CharField(source="department.name", default=None, read_only=True)
    sent_by = serializers.CharField(source="sent_by.full_name", read_only=True)
    read_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Broadcast
        fields = ["id", "title", "body", "link", "audience", "audience_label", "department", "department_name",
                  "recipient_count", "read_count", "sent_by", "created_at"]
        read_only_fields = fields


LINK_RE = re.compile(r"/member(/[A-Za-z0-9_-]+)*/?")


class SendBroadcastSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=5000)
    link = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    audience = serializers.ChoiceField(choices=Broadcast.Audience.choices)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    members = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all(), many=True, required=False)

    def validate_link(self, value):
        # Links are member-portal routes, never URLs: letters, digits, "-", "_" and "/" only,
        # so nothing like "//host" or "/member/..\host" can turn into an off-site redirect.
        if value and not LINK_RE.fullmatch(value):
            raise serializers.ValidationError("Use a member-portal path such as /member/savings.")
        return value


class BroadcastViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Messages officers have sent to members (the sent-items list), and sending a new one."""

    serializer_class = BroadcastSerializer
    filterset_fields = ["audience"]
    search_fields = ["title", "body"]
    permission_map = {"*": (P.SEND_NOTIFICATIONS,)}

    def get_queryset(self):
        return (
            Broadcast.objects.select_related("sent_by", "department")
            .annotate(read_count=Count("notifications", filter=Q(notifications__read_at__isnull=False)))
            .order_by("-created_at")
        )

    @extend_schema(request=SendBroadcastSerializer, responses={201: BroadcastSerializer})
    def create(self, request):
        serializer = SendBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        broadcast = services.send_broadcast(request.user, **serializer.validated_data)
        return Response(BroadcastSerializer(self.get_queryset().get(pk=broadcast.pk)).data, status=status.HTTP_201_CREATED)
