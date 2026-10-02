from django.contrib import admin

from apps.common.admin import AuditedAdminMixin

from .models import Announcement, Notification


@admin.register(Announcement)
class AnnouncementAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "audience", "is_important", "publish_at", "expires_at", "created_by")
    list_filter = ("audience", "is_important")
    search_fields = ("title", "body")
    readonly_fields = ("created_by",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(AuditedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "recipient", "category", "created_at", "read_at")
    list_filter = ("category",)
    search_fields = ("title", "recipient__email")
