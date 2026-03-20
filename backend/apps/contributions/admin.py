from django.contrib import admin
from .models import Contribution

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    # ✅ Matches your exact model fields
    list_display = ('member', 'type', 'amount', 'status', 'due_date', 'reference_id')
    
    # ✅ Adds helpful side-panel filters
    list_filter = ('status', 'type', 'due_date')
    
    # ✅ Lets you search by ID, name, or the auto-generated reference number
    search_fields = ('member__membership_id', 'member__first_name', 'member__last_name', 'reference_id')
    
    # Protect the auto-generated reference ID from being accidentally edited
    readonly_fields = ('reference_id',)
    
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected contributions as PAID')
    def mark_as_paid(self, request, queryset):
        # We use 'PAID' to match your StatusChoices
        queryset.update(status='PAID')