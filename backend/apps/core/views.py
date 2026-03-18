from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SystemSetting, Notification
from .serializers import SystemSettingSerializer, NotificationSerializer
from apps.accounts.permissions import IsManagerOrAdmin 

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsManagerOrAdmin()]

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Sort by newest first so the list makes sense
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Returns just the number of unread alerts for the red dot."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Returns the 5 most recent unread notifications for the Navbar."""
        notifications = self.get_queryset().filter(is_read=False)[:5]
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "all marked as read"})