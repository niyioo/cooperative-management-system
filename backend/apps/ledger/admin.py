from django.contrib import admin

from apps.common.admin import ReadOnlyAdminMixin

from .models import Transaction, TransactionBatch

# The ledger is append-only. Entries are created, approved and reversed only
# through the service layer (officer portal), never edited here.


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "value_date", "member", "txn_type", "entry_side", "amount", "status", "created_by", "approved_by")
    list_filter = ("status", "txn_type", "entry_side")
    search_fields = ("reference", "external_reference", "member__membership_number", "member__last_name")
    date_hierarchy = "value_date"
    list_select_related = ("member", "created_by", "approved_by")


class BatchTransactionInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = Transaction
    fk_name = "batch"
    extra = 0
    fields = ("reference", "member", "txn_type", "amount", "status")
    readonly_fields = fields
    show_change_link = True


@admin.register(TransactionBatch)
class TransactionBatchAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "batch_type", "period", "line_count", "total_amount", "status", "created_by", "approved_by")
    list_filter = ("status", "batch_type")
    search_fields = ("reference", "description")
    inlines = [BatchTransactionInline]
