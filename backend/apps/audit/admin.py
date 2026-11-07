from django.contrib import admin

from apps.common.admin import ReadOnlyAdminMixin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("timestamp", "actor_repr", "action", "object_type", "object_repr", "ip_address")
    list_filter = ("action", "object_type")
    search_fields = ("actor_repr", "action", "object_id", "object_repr")
    date_hierarchy = "timestamp"
