from django.apps import apps as django_apps
from rest_framework import serializers

from .models import Role, User
from .permissions import is_officer, member_profile
from .perms import ALL_PERMISSIONS


def user_payload(user):
    """What the SPA needs to know about the signed-in user: identity, portals, permissions."""
    officer = is_officer(user)
    member = member_profile(user)
    portals = (["officer"] if officer else []) + (["member"] if member else [])
    return {
        "id": str(user.pk),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "phone": user.phone,
        "must_change_password": user.must_change_password,
        "is_officer": officer,
        "roles": sorted(user.groups.values_list("name", flat=True)) if officer else [],
        "permissions": sorted(user.get_all_permissions() & ALL_PERMISSIONS) if officer else [],
        "member": (
            {
                "id": str(member.pk),
                "membership_number": member.membership_number,
                "full_name": member.full_name,
                "status": member.status,
            }
            if member
            else None
        ),
        "portals": portals,
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class MemberSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    membership_number = serializers.CharField()
    full_name = serializers.CharField()
    status = serializers.CharField()


class CurrentUserSerializer(serializers.Serializer):
    """Documents the shape returned by user_payload()."""

    id = serializers.UUIDField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.CharField()
    phone = serializers.CharField()
    must_change_password = serializers.BooleanField()
    is_officer = serializers.BooleanField()
    roles = serializers.ListField(child=serializers.CharField())
    permissions = serializers.ListField(child=serializers.CharField())
    member = MemberSummarySerializer(allow_null=True)
    portals = serializers.ListField(child=serializers.ChoiceField(choices=["officer", "member"]))


class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    access_expires_in = serializers.IntegerField(help_text="Seconds until the access token expires.")
    user = CurrentUserSerializer()


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, help_text="Email address or membership number.")
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenPasswordSerializer(serializers.Serializer):
    """Password reset confirmation and account activation."""

    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------

class RoleSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name"]


class OfficerSerializer(serializers.ModelSerializer):
    roles = RoleSummarySerializer(source="groups", many=True, read_only=True)
    is_activated = serializers.SerializerMethodField()
    membership_number = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "is_active",
            "is_superuser",
            "is_activated",
            "membership_number",
            "roles",
            "last_login",
            "date_joined",
        ]

    def get_is_activated(self, obj) -> bool:
        return obj.has_usable_password()

    def get_membership_number(self, obj) -> str | None:
        member = member_profile(obj)
        return member.membership_number if member else None


class OfficerCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    roles = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True)


class OfficerUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)


class OfficerRolesSerializer(serializers.Serializer):
    roles = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all(), many=True)


class RevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

class RoleSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()
    is_system = serializers.SerializerMethodField()
    officer_count = serializers.IntegerField(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "name", "description", "is_system", "officer_count", "permissions"]

    def _profile(self, obj):
        return getattr(obj, "profile", None)

    def get_description(self, obj) -> str:
        profile = self._profile(obj)
        return profile.description if profile else ""

    def get_is_system(self, obj) -> bool:
        profile = self._profile(obj)
        return bool(profile and profile.is_system)

    def get_permissions(self, obj) -> list[str]:
        return sorted(f"{p.content_type.app_label}.{p.codename}" for p in obj.permissions.all())


class RoleWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True)
    permissions = serializers.ListField(child=serializers.CharField(max_length=150), allow_empty=True)


class PermissionEntrySerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class PermissionModuleSerializer(serializers.Serializer):
    module = serializers.CharField()
    label = serializers.CharField()
    permissions = PermissionEntrySerializer(many=True)


class TemporaryPasswordSerializer(serializers.Serializer):
    temporary_password = serializers.CharField()
    message = serializers.CharField()


def permission_catalogue(permissions):
    """Group Permission rows by module for the role editor."""
    groups = {}
    for perm in permissions:
        label = perm.content_type.app_label
        if label not in groups:
            groups[label] = {
                "module": label,
                "label": django_apps.get_app_config(label).verbose_name,
                "permissions": [],
            }
        groups[label]["permissions"].append({"code": f"{label}.{perm.codename}", "name": perm.name})
    return list(groups.values())
