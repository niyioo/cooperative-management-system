from django.contrib import admin

from apps.common.admin import AuditedAdminMixin, NoDeleteAdminMixin

from .models import Member, MemberDocument, MembershipStatusChange, NextOfKin


class NextOfKinInline(admin.StackedInline):
    model = NextOfKin
    extra = 0


class MemberDocumentInline(admin.TabularInline):
    model = MemberDocument
    extra = 0
    fields = ("document_type", "title", "file", "verified_by", "verified_at", "created_at")
    readonly_fields = ("created_at",)


class MembershipStatusChangeInline(admin.TabularInline):
    model = MembershipStatusChange
    fk_name = "member"
    extra = 0
    can_delete = False
    fields = ("created_at", "from_status", "to_status", "reason", "changed_by")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Member)
class MemberAdmin(AuditedAdminMixin, NoDeleteAdminMixin, admin.ModelAdmin):
    list_display = ("membership_number", "full_name", "department", "phone", "status", "date_joined")
    list_filter = ("status", "department", "employment_status", "gender")
    search_fields = (
        "membership_number",
        "first_name",
        "last_name",
        "phone",
        "staff_number",
        "ippis_number",
        "user__email",
    )
    autocomplete_fields = ("user", "department")
    readonly_fields = ("created_at", "updated_at", "created_by", "closed_at")
    inlines = [NextOfKinInline, MemberDocumentInline, MembershipStatusChangeInline]
    fieldsets = (
        ("Membership", {"fields": ("user", "membership_number", "date_joined", "status", "status_reason", "closed_at")}),
        (
            "Personal",
            {
                "fields": (
                    "title",
                    ("first_name", "middle_name", "last_name"),
                    ("gender", "date_of_birth", "marital_status"),
                    ("phone", "alt_phone"),
                    "residential_address",
                    ("state_of_origin", "lga"),
                    "photo",
                )
            },
        ),
        (
            "Employment",
            {
                "fields": (
                    ("staff_number", "ippis_number"),
                    ("department", "unit"),
                    ("designation", "grade_level"),
                    ("employment_date", "employment_status"),
                )
            },
        ),
        ("Bank details", {"fields": ("bank_name", "bank_account_number", "bank_account_name")}),
        ("Record", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(MembershipStatusChange)
class MembershipStatusChangeAdmin(admin.ModelAdmin):
    list_display = ("member", "from_status", "to_status", "reason", "changed_by", "created_at")
    list_filter = ("to_status",)
    search_fields = ("member__membership_number", "member__last_name")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
