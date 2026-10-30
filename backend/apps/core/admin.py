from django.contrib import admin

from .models import Notification, SystemSetting


class ReadOnlyAdminMixin:
    """
    For money records that may only change through the service layer, so the
    balances always match their transactions. Visible for audit, never editable.
    Admin actions (which call the services) still work.
    """

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('cooperative_name', 'currency', 'share_unit_price', 'updated_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'is_read')
