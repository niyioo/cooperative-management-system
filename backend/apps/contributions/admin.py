from django.contrib import admin, messages
from rest_framework.exceptions import APIException

from apps.core.admin import ReadOnlyAdminMixin

from . import services
from .models import Contribution


@admin.register(Contribution)
class ContributionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('member', 'type', 'amount', 'status', 'due_date', 'reference_id')
    list_filter = ('status', 'type', 'due_date')
    search_fields = ('member__membership_id', 'member__first_name', 'member__last_name', 'reference_id')
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected contributions as PAID (records the income)')
    def mark_as_paid(self, request, queryset):
        done = 0
        for contribution in queryset:
            try:
                services.mark_paid(contribution, by=request.user)
                done += 1
            except APIException as exc:
                self.message_user(request, f"{contribution.reference_id}: {exc.detail}", level=messages.WARNING)
        if done:
            self.message_user(request, f"Marked {done} as paid.", level=messages.SUCCESS)
