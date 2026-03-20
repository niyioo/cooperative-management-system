from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    # What columns to show in the list view
    list_display = ('email', 'role', 'first_name', 'last_name', 'is_staff', 'is_active')
    # Filters on the right side
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    # Which fields can be searched
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)

    # These organize the detail view (editing a user)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    
    # Required for Custom User Models
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'is_staff', 'is_active'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)