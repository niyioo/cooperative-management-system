"""/api/v1/me/notifications/ and /api/v1/me/announcements/"""
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from apps.accounts.permissions import MemberAPIMixin, member_scoped

from ..models import Announcement, Notification
from ..selectors import visible_announcements


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "category", "title", "body", "link", "is_read", "read_at", "created_at"]


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "is_important", "publish_at", "expires_at"]


class MyNotificationViewSet(MemberAPIMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    lookup_value_regex = r"[0-9a-fA-F-]{36}"
    filterset_fields = ["category"]

    @member_scoped(Notification)
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at")

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(request=None, responses={200: OpenApiResponse(description="{'marked': n}")})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        marked = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now(), updated_at=timezone.now())
        return Response({"marked": marked})

    @extend_schema(responses={200: OpenApiResponse(description="{'unread': n}")})
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(read_at__isnull=True).count()})


class MyAnnouncementsView(MemberAPIMixin, ListAPIView):
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        return visible_announcements()
