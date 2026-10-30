from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """The ledger is permanent; corrections are reversing entries made in the app."""

    list_display = ('date', 'reference_id', 'type', 'category', 'amount', 'member', 'reverses')
    list_filter = ('type', 'category', 'date')
    search_fields = ('description', 'reference_id')
    date_hierarchy = 'date'
