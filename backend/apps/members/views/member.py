"""
/api/v1/me/ — the signed-in member's own dashboard and profile.

Every view in the member portal resolves the member from request.user; no
endpoint accepts another member's id (BR-16).
"""
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import MemberAPIMixin
from apps.audit.services import record
from apps.common.serializers import money_to_str

from ..selectors import member_dashboard
from ..serializers import MemberDetailSerializer, clean_phone


class DashboardView(MemberAPIMixin, APIView):
    @extend_schema(responses={200: OpenApiResponse(description="Summary cards, recent activity and announcements")})
    def get(self, request):
        return Response(money_to_str(member_dashboard(self.member)))


class MyProfileSerializer(MemberDetailSerializer):
    """The member's own record, without officer-only fields."""

    class Meta(MemberDetailSerializer.Meta):
        fields = [
            f for f in MemberDetailSerializer.Meta.fields
            if f not in {"status_history", "created_by", "status_reason", "document_count"}
        ]


class ContactUpdateSerializer(serializers.Serializer):
    """Members may update their own contact details; everything else goes through the secretariat."""

    phone = serializers.CharField(max_length=20, required=False)
    alt_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    residential_address = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        value = clean_phone(value)
        if not value:
            raise serializers.ValidationError("A phone number is required.")
        return value

    def validate_alt_phone(self, value):
        return clean_phone(value)


class ProfileView(MemberAPIMixin, APIView):
    @extend_schema(responses={200: MyProfileSerializer})
    def get(self, request):
        return Response(MyProfileSerializer(self.member).data)

    @extend_schema(request=ContactUpdateSerializer, responses={200: MyProfileSerializer})
    def patch(self, request):
        serializer = ContactUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        member = self.member
        changes = {f: [getattr(member, f), v] for f, v in serializer.validated_data.items() if getattr(member, f) != v}
        if changes:
            with transaction.atomic():
                for field, (_, value) in changes.items():
                    setattr(member, field, value)
                member.save(update_fields=[*changes, "updated_at"])
                if "phone" in changes:
                    member.user.phone = member.phone
                    member.user.save(update_fields=["phone", "updated_at"])
                record("member.contact_updated", actor=request.user, obj=member, changes=changes)
        return Response(MyProfileSerializer(member).data)


class PhotoView(MemberAPIMixin, APIView):
    @extend_schema(responses={(200, "image/*"): OpenApiResponse(description="The member's photo")})
    def get(self, request):
        if not self.member.photo:
            raise NotFound("No photo on record.")
        response = FileResponse(self.member.photo.open("rb"))
        response["Cache-Control"] = "private, max-age=300"
        return response
