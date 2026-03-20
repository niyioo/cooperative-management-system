from django.contrib import admin
from .models import Contribution, MemberAssessment

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'frequency', 'is_mandatory')
    list_editable = ('is_mandatory',)

@admin.register(MemberAssessment)
class MemberAssessmentAdmin(admin.ModelAdmin):
    list_display = ('member', 'contribution', 'amount', 'status', 'due_date')
    list_filter = ('status', 'due_date')
    search_fields = ('member__membership_id', 'contribution__name')
    actions = ['mark_as_paid']

    @admin.action(description='Mark selected assessments as Paid')
    def mark_as_paid(self, request, queryset):
        queryset.update(status='PAID')