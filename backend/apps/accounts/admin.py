from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from apps.common.admin import AuditedAdminMixin

from .models import Role, RoleProfile, User


@admin.register(User)
class EmdiUserAdmin(AuditedAdminMixin, UserAdmin):
    ordering = ("last_name", "first_name")
    list_display = ("email", "full_name", "is_staff_officer", "is_active", "last_login")
    list_filter = ("is_staff_officer", "is_active", "is_staff", "groups")
    search_fields = ("email", "first_name", "last_name", "phone")
    readonly_fields = ("last_login", "date_joined", "last_password_change", "updated_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        (
            "Access",
            {
                "fields": (
                    "is_active",
                    "is_staff_officer",
                    "is_staff",
                    "is_superuser",
                    "must_change_password",
                    "groups",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "last_password_change", "date_joined", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )
    filter_horizontal = ("groups",)

    def has_delete_permission(self, request, obj=None):
        return False


class RoleProfileInline(admin.StackedInline):
    model = RoleProfile
    can_delete = False


admin.site.unregister(Group)


@admin.register(Role)
class RoleAdmin(AuditedAdminMixin, GroupAdmin):
    inlines = [RoleProfileInline]
    list_display = ("name", "permission_count")

    @admin.display(description="Permissions")
    def permission_count(self, obj):
        return obj.permissions.count()

    def has_delete_permission(self, request, obj=None):
        if obj is not None and getattr(getattr(obj, "profile", None), "is_system", False):
            return False
        return super().has_delete_permission(request, obj)
