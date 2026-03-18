from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import SystemSetting, Notification
from .serializers import SystemSettingSerializer, NotificationSerializer
from apps.accounts.permissions import IsManagerOrAdmin # Adjust path as needed

class SystemSettingViewSet(viewsets.ModelViewSet):
    """
    Manages global cooperative settings.
    Only Managers/Admins can edit these.
    """
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsManagerOrAdmin()]

class NotificationViewSet(viewsets.ModelViewSet):
    """
    Manages user notifications.
    Users can only see and modify their own notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Always filter so a user only sees their personal alerts
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Marks a single notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Marks all of the user's notifications as read."""
        notifications = self.get_queryset().filter(is_read=False)
        notifications.update(is_read=True)
        return Response({"status": "all marked as read"})