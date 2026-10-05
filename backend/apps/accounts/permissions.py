"""
Access control for the two portals (ARCHITECTURE.md §3, §11).

Officer views:  class MyView(OfficerAPIMixin, …) with a `permission_map`
                mapping each action (or HTTP method) to required permissions.
                Unmapped actions are DENIED (fail closed).
Member views:   class MyView(MemberAPIMixin, …); use `self.member`, never an ID
                from the request.

Services re-check permissions with require_perm() so non-HTTP callers
(imports, management commands) are held to the same rules.
"""
import logging
from functools import wraps

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.common.exceptions import DomainError

logger = logging.getLogger(__name__)


class AnyPerm(tuple):
    """permission_map value satisfied by holding any one of the permissions."""

    def __new__(cls, *perms):
        return super().__new__(cls, perms)


def is_officer(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or user.is_staff_officer)
    )


def member_profile(user):
    """The user's Member, or None. (Reverse one-to-one raises when missing.)"""
    if not (user and user.is_authenticated):
        return None
    return getattr(user, "member", None)


def can_use_portal(user):
    return bool(user and user.is_active and (is_officer(user) or member_profile(user) is not None))


def _require_password_current(user):
    if user.must_change_password:
        raise PermissionDenied(
            detail="You must change your password before continuing.",
            code="password_change_required",
        )


class IsOfficer(BasePermission):
    message = "This area is for cooperative officers only."

    def has_permission(self, request, view):
        user = request.user
        if not is_officer(user):
            return False
        _require_password_current(user)

        get_required = getattr(view, "get_required_permissions", None)
        required = get_required(request) if get_required else None
        if required is None:
            logger.error("Officer view %s has no permission mapping for this action; denying.", type(view).__name__)
            return False
        if isinstance(required, AnyPerm):
            return any(user.has_perm(p) for p in required)
        return user.has_perms(required)


class IsMemberSelf(BasePermission):
    message = "This area is for cooperative members."

    def has_permission(self, request, view):
        user = request.user
        if member_profile(user) is None or not user.is_active:
            return False
        _require_password_current(user)
        return True


class OfficerAPIMixin:
    """
    permission_map = {"list": (P.VIEW_MEMBER,), "create": (P.ADD_MEMBER,), "*": (…)}
    Keys are viewset actions, or lower-case HTTP methods for plain APIViews.
    "action:method" (e.g. "documents:post") targets one method of a
    multi-method action. "*" is the fallback; () means "any officer".
    Anything unmapped is denied.
    """

    permission_classes = [IsOfficer]
    permission_map = {}

    def get_required_permissions(self, request):
        method = request.method.lower()
        action_name = getattr(self, "action", None)
        for key in (f"{action_name}:{method}", action_name or method):
            if key in self.permission_map:
                return self.permission_map[key]
        return self.permission_map.get("*")


class MemberAPIMixin:
    permission_classes = [IsMemberSelf]

    @property
    def member(self):
        return self.request.user.member


def member_scoped(model):
    """
    Decorator for a member view's get_queryset(). The API schema generator
    calls views without a signed-in member; give it an empty queryset.
    """

    def decorator(get_queryset):
        @wraps(get_queryset)
        def wrapper(self):
            if getattr(self, "swagger_fake_view", False):
                return model.objects.none()
            return get_queryset(self)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Service-layer guards
# ---------------------------------------------------------------------------

def require_perm(user, *perms):
    """Raise unless `user` holds every permission. Use at the top of each service."""
    missing = [p for p in perms if not user.has_perm(p)]
    if missing:
        raise DjangoPermissionDenied("You do not have permission to perform this action.")


def assert_not_self(actor, member, what="act on"):
    """BR-18: officers never act on their own member records."""
    if member is not None and member.user_id == actor.pk:
        raise DomainError(
            f"You cannot {what} your own member record. Another officer must do this.",
            code="self_dealing",
        )
