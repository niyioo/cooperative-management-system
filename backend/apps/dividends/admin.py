from django.contrib import admin

from apps.common.admin import ReadOnlyAdminMixin

from .models import DividendCalculationRun, DividendCycle, MemberDividend

# Calculation, approval and payment run through the officer portal's service
# layer; the Django admin only displays dividend records.


class DividendCalculationRunInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = DividendCalculationRun
    extra = 0
    fields = ("run_number", "status", "member_count", "total_basis", "total_gross", "total_net", "run_by", "created_at")
    readonly_fields = fields


@admin.register(DividendCycle)
class DividendCycleAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("reference", "financial_year", "basis", "rate", "cutoff_date", "status", "approved_by", "paid_at")
    list_filter = ("status", "basis")
    inlines = [DividendCalculationRunInline]


@admin.register(MemberDividend)
class MemberDividendAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("member", "cycle", "run", "basis_amount", "gross_amount", "net_amount", "status", "paid_at")
    list_filter = ("status", "cycle")
    search_fields = ("member__membership_number", "member__last_name")
