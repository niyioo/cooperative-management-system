from django.contrib import admin
from .models import LedgerEntry

@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'type', 'category', 'amount', 'description')
    list_filter = ('type', 'category', 'date')
    search_fields = ('description', 'reference_id')
    date_hierarchy = 'date' # Adds a nice date drill-down at the top