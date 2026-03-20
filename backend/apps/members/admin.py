from django.contrib import admin
from .models import Member

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # What you see in the table list
    list_display = ('membership_id', 'user_email', 'full_name', 'status', 'joined_date')
    list_filter = ('status', 'created_at')
    search_fields = ('membership_id', 'user__email', 'first_name', 'last_name')
    readonly_fields = ('membership_id', 'created_at', 'updated_at')

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = 'Name'

    # Organize the edit page
    fieldsets = (
        ('Identification', {'fields': ('membership_id', 'user')}),
        ('Personal Details', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Status & Verification', {'fields': ('status',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )