from django.contrib import admin
from .models import Member, NextOfKin, MemberDocument

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # ✅ Replaced joined_date with created_at
    list_display = ('membership_id', 'first_name', 'last_name', 'phone_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('membership_id', 'first_name', 'last_name', 'phone_number', 'user__email')
    readonly_fields = ('membership_id',)

@admin.register(NextOfKin)
class NextOfKinAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'member', 'relationship', 'phone_number')
    search_fields = ('full_name', 'member__membership_id')

@admin.register(MemberDocument)
class MemberDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_type', 'member', 'is_verified', 'uploaded_at')
    list_filter = ('document_type', 'is_verified')
    search_fields = ('member__membership_id',)