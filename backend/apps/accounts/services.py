"""
Authentication, officer access and role management. Every state change is
audited, and every officer action is permission-checked here as well as in
the view.

Anti-escalation rules for officer and role management:
  * Officers cannot change their own roles or revoke their own access.
  * You can only grant permissions you hold yourself.
  * You can only manage officers (and edit roles) whose permissions you hold.
  * At least one active officer must keep manage_roles + manage_officers.
"""
import secrets
from collections import defaultdict

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission, update_last_login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from apps.audit.services import record
from apps.common.exceptions import DomainError

from .emails import send_activation_email, send_password_reset_email
from .models import Role, RoleProfile
from .permissions import can_use_portal, is_officer, require_perm
from .perms import ADMINISTRATION_PERMISSIONS, ALL_PERMISSIONS, P
from .tokens import activation_token, decode_uid, password_reset_token

User = get_user_model()

INVALID_CREDENTIALS = "The email/membership number or password is incorrect."


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_for_portal(request, *, identifier, password):
    user = authenticate(request, username=identifier, password=password)
    if user is None or not can_use_portal(user):
        record("auth.login_failed", metadata={"identifier": (identifier or "")[:254]})
        raise AuthenticationFailed(INVALID_CREDENTIALS, code="invalid_credentials")
    update_last_login(None, user)
    record("auth.login_succeeded", actor=user, obj=user)
    return user


def consume_refresh_token(raw_token):
    """
    Validate a refresh token and blacklist it (rotation). Returns the user.
    Raises TokenError or AuthenticationFailed when the session is no longer valid.
    """
    token = RefreshToken(raw_token)  # signature, expiry and blacklist checks
    user = User.objects.filter(pk=token.payload.get(jwt_settings.USER_ID_CLAIM)).first()
    password_unchanged = user is not None and token.payload.get(
        jwt_settings.REVOKE_TOKEN_CLAIM
    ) == get_md5_hash_password(user.password)
    if not (password_unchanged and can_use_portal(user)):
        raise AuthenticationFailed("Your session has ended. Please sign in again.", code="session_expired")
    token.blacklist()
    return user


def end_session(raw_token):
    """Blacklist the refresh token on logout. Invalid or expired tokens are ignored."""
    if not raw_token:
        return
    try:
        token = RefreshToken(raw_token)
    except TokenError:
        return  # already invalid or expired: nothing to end
    user = User.objects.filter(pk=token.payload.get(jwt_settings.USER_ID_CLAIM)).first()
    token.blacklist()
    if user is not None:
        record("auth.logout", actor=user, obj=user)


def revoke_refresh_tokens(user):
    outstanding = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=t) for t in outstanding], ignore_conflicts=True
    )


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def validate_new_password(password, user, field="new_password"):
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise DomainError(exc.messages[0], code="weak_password", fields={field: exc.messages}) from exc


def _set_password(user, new_password, *, must_change=False):
    user.set_password(new_password)
    user.must_change_password = must_change
    user.save(update_fields=["password", "last_password_change", "must_change_password", "updated_at"])
    revoke_refresh_tokens(user)


@transaction.atomic
def change_password(user, *, current_password, new_password):
    if not user.check_password(current_password):
        raise DomainError(
            "Your current password is incorrect.",
            code="invalid_password",
            fields={"current_password": ["Your current password is incorrect."]},
        )
    if current_password == new_password:
        raise DomainError(
            "Choose a password different from your current one.",
            code="password_reused",
            fields={"new_password": ["Choose a password different from your current one."]},
        )
    validate_new_password(new_password, user)
    _set_password(user, new_password)
    record("auth.password_changed", actor=user, obj=user)


def request_password_reset(email):
    """Always succeeds from the caller's point of view, so accounts can't be discovered."""
    email = (email or "").strip()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    record("auth.password_reset_requested", metadata={"email": email[:254], "account_found": user is not None})
    if user is None:
        return
    if user.has_usable_password():
        send_password_reset_email(user)
    else:
        # Never activated: a fresh activation link is what they need.
        send_activation_email(user)


@transaction.atomic
def reset_password(*, uid, token, new_password):
    user = decode_uid(uid)
    if user is None or not user.is_active or not password_reset_token.check_token(user, token):
        raise DomainError(
            "This password reset link is invalid or has expired. Please request a new one.",
            code="invalid_token",
        )
    validate_new_password(new_password, user)
    _set_password(user, new_password)
    record("auth.password_reset_completed", actor=user, obj=user)


@transaction.atomic
def activate_account(*, uid, token, new_password):
    user = decode_uid(uid)
    if (
        user is None
        or not user.is_active
        or user.has_usable_password()
        or not activation_token.check_token(user, token)
    ):
        raise DomainError(
            "This activation link is invalid, has expired or has already been used.",
            code="invalid_token",
        )
    validate_new_password(new_password, user)
    _set_password(user, new_password)
    record("auth.account_activated", actor=user, obj=user)


def generate_temporary_password(length=12):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"  # no look-alikes
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in candidate) and any(c.islower() for c in candidate) and any(c.isupper() for c in candidate):
            return candidate


@transaction.atomic
def issue_temporary_password(actor, user, *, permission):
    """
    Fallback when email is unavailable: a one-time password the person must
    change at next login. The password is returned once and never stored or logged.
    """
    require_perm(actor, permission)
    _assert_not_self(actor, user, "Use 'change password' for your own account.")
    if is_officer(user):
        _assert_can_manage_officer(actor, user)
    password = generate_temporary_password()
    _set_password(user, password, must_change=True)
    record("auth.temporary_password_issued", actor=actor, obj=user)
    return password


@transaction.atomic
def resend_activation(actor, user, *, permission):
    require_perm(actor, permission)
    if not user.is_active:
        raise DomainError("This account is deactivated.", code="inactive_account")
    if user.has_usable_password():
        raise DomainError("This account has already been activated.", code="already_activated")
    record("auth.activation_sent", actor=actor, obj=user)
    transaction.on_commit(lambda: send_activation_email(user))


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def permission_codes(permissions):
    """Queryset/iterable of Permission -> {"app_label.codename"}."""
    if hasattr(permissions, "values_list"):
        return {f"{a}.{c}" for a, c in permissions.values_list("content_type__app_label", "codename")}
    return {f"{p.content_type.app_label}.{p.codename}" for p in permissions}


def role_permissions(roles):
    return permission_codes(Permission.objects.filter(group__in=list(roles)))


def actor_permissions(actor):
    if actor.is_superuser:
        return set(ALL_PERMISSIONS)
    return role_permissions(actor.groups.all())


def resolve_permissions(codes):
    codes = set(codes)
    unknown = sorted(codes - ALL_PERMISSIONS)
    if unknown:
        raise DomainError(
            f"Unknown permission: {', '.join(unknown)}.",
            code="unknown_permission",
            fields={"permissions": [f"Unknown permission: {c}" for c in unknown]},
        )
    if not codes:
        return []
    query = Q()
    for code in codes:
        app_label, codename = code.split(".", 1)
        query |= Q(content_type__app_label=app_label, codename=codename)
    return list(Permission.objects.filter(query).select_related("content_type"))


def _assert_not_self(actor, user, message):
    if actor.pk == user.pk:
        raise DomainError(message, code="self_action")


def _assert_actor_holds(actor, codes, message="You can only grant permissions you hold yourself."):
    missing = sorted(set(codes) - actor_permissions(actor))
    if missing:
        raise DomainError(message, code="privilege_escalation", fields={"permissions": missing})


def _assert_can_manage_officer(actor, officer):
    if officer.is_superuser and not actor.is_superuser:
        raise DomainError(
            "Superuser accounts can only be managed from the support console.", code="superuser_account"
        )
    _assert_actor_holds(
        actor,
        role_permissions(officer.groups.all()),
        "This officer holds permissions you do not have, so you cannot manage their access.",
    )


def _assert_administrator_remains(*, user_roles=None, role_perms=None, removed_role_ids=()):
    """
    Simulate a change and make sure at least one active officer could still
    manage roles and officers afterwards. An active superuser always counts,
    since they can recover access from the support console.

    user_roles: {user_id: [roles]} after the change
    role_perms: {role_id: {codes}} after the change
    """
    if User.objects.filter(is_active=True, is_superuser=True).exists():
        return
    user_roles = user_roles or {}
    perms_by_role = defaultdict(set)
    rows = Permission.objects.filter(group__isnull=False).values_list(
        "group__id", "content_type__app_label", "codename"
    )
    for group_id, app_label, codename in rows:
        perms_by_role[group_id].add(f"{app_label}.{codename}")
    perms_by_role.update(role_perms or {})

    for officer in User.objects.filter(is_active=True, is_staff_officer=True).prefetch_related("groups"):
        roles = user_roles.get(officer.pk, list(officer.groups.all()))
        effective = set()
        for role in roles:
            if role.pk not in removed_role_ids:
                effective |= perms_by_role[role.pk]
        if ADMINISTRATION_PERMISSIONS <= effective:
            return
    raise DomainError(
        "This change would leave no active officer able to manage roles and officers.",
        code="last_administrator",
    )


def _role_names(roles):
    return sorted(r.name for r in roles)


# ---------------------------------------------------------------------------
# Officer access
# ---------------------------------------------------------------------------

@transaction.atomic
def grant_officer_access(actor, *, email, first_name, last_name, roles, phone=""):
    """
    Make someone an officer. If the email already belongs to a user (typically
    a member), that account is promoted; otherwise a new account is created and
    an activation email is sent.
    """
    require_perm(actor, P.MANAGE_OFFICERS)
    roles = list(roles)
    if not roles:
        raise DomainError("Select at least one role.", code="roles_required", fields={"roles": ["Select at least one role."]})
    _assert_actor_holds(actor, role_permissions(roles))

    user = User.objects.filter(email__iexact=email.strip()).first()
    created = user is None
    if created:
        user = User.objects.create_user(email=email, first_name=first_name, last_name=last_name, phone=phone)
    else:
        _assert_not_self(actor, user, "You cannot change your own officer access.")
        if not user.is_active:
            raise DomainError("This account is deactivated.", code="inactive_account")
        if is_officer(user):
            raise DomainError(
                "This person is already an officer. Change their roles instead.", code="already_officer"
            )

    user.is_staff_officer = True
    user.save(update_fields=["is_staff_officer", "updated_at"])
    user.groups.set(roles)
    record(
        "officer.access_granted",
        actor=actor,
        obj=user,
        changes={"roles": [[], _role_names(roles)]},
        metadata={"account_created": created},
    )
    if created:
        transaction.on_commit(lambda: send_activation_email(user))
    return user, created


@transaction.atomic
def update_officer_profile(actor, officer, **fields):
    require_perm(actor, P.MANAGE_OFFICERS)
    if actor.pk != officer.pk:
        _assert_can_manage_officer(actor, officer)
    changes = {}
    for name in ("first_name", "last_name", "phone"):
        if name in fields and fields[name] != getattr(officer, name):
            changes[name] = [getattr(officer, name), fields[name]]
            setattr(officer, name, fields[name])
    if changes:
        officer.save(update_fields=[*changes, "updated_at"])
        record("officer.updated", actor=actor, obj=officer, changes=changes)
    return officer


@transaction.atomic
def set_officer_roles(actor, officer, roles):
    require_perm(actor, P.MANAGE_OFFICERS)
    _assert_not_self(actor, officer, "You cannot change your own roles. Ask another administrator.")
    if not officer.is_staff_officer:
        raise DomainError("This person is not an officer.", code="not_officer")
    roles = list(roles)
    if not roles:
        raise DomainError(
            "An officer needs at least one role. To remove access completely, revoke it instead.",
            code="roles_required",
            fields={"roles": ["Select at least one role."]},
        )
    _assert_can_manage_officer(actor, officer)
    _assert_actor_holds(actor, role_permissions(roles))
    _assert_administrator_remains(user_roles={officer.pk: roles})

    before = _role_names(officer.groups.all())
    officer.groups.set(roles)
    record("officer.roles_changed", actor=actor, obj=officer, changes={"roles": [before, _role_names(roles)]})
    return officer


@transaction.atomic
def revoke_officer_access(actor, officer, *, reason=""):
    """Remove officer access. The account itself (and any member profile) stays."""
    require_perm(actor, P.MANAGE_OFFICERS)
    _assert_not_self(actor, officer, "You cannot revoke your own officer access.")
    if officer.is_superuser:
        raise DomainError(
            "Superuser accounts can only be managed from the support console.", code="superuser_account"
        )
    if not officer.is_staff_officer:
        raise DomainError("This person is not an officer.", code="not_officer")
    _assert_can_manage_officer(actor, officer)
    _assert_administrator_remains(user_roles={officer.pk: []})

    before = _role_names(officer.groups.all())
    officer.groups.clear()
    officer.is_staff_officer = False
    officer.save(update_fields=["is_staff_officer", "updated_at"])
    record(
        "officer.access_revoked",
        actor=actor,
        obj=officer,
        changes={"roles": [before, []]},
        metadata={"reason": reason},
    )
    return officer


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

def _assert_unique_role_name(name, exclude_pk=None):
    qs = Group.objects.filter(name__iexact=name)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise DomainError(
            "A role with this name already exists.",
            code="duplicate_name",
            fields={"name": ["A role with this name already exists."]},
        )


@transaction.atomic
def create_role(actor, *, name, permissions, description=""):
    require_perm(actor, P.MANAGE_ROLES)
    name = name.strip()
    perms = resolve_permissions(permissions)
    codes = permission_codes(perms)
    _assert_actor_holds(actor, codes)
    _assert_unique_role_name(name)

    role = Role.objects.create(name=name)
    RoleProfile.objects.create(group=role, description=description, is_system=False)
    role.permissions.set(perms)
    record("role.created", actor=actor, obj=role, changes={"permissions": [[], sorted(codes)]})
    return role


@transaction.atomic
def update_role(actor, role, *, name=None, description=None, permissions=None):
    require_perm(actor, P.MANAGE_ROLES)
    profile, _ = RoleProfile.objects.get_or_create(group=role)
    current = role_permissions([role])
    # Editing a role affects everyone who holds it, so the editor must hold all of its permissions.
    _assert_actor_holds(actor, current, "This role has permissions you do not hold, so you cannot edit it.")
    changes = {}

    if name is not None and name.strip() != role.name:
        if profile.is_system:
            raise DomainError("System roles cannot be renamed.", code="system_role")
        _assert_unique_role_name(name.strip(), exclude_pk=role.pk)
        changes["name"] = [role.name, name.strip()]
        role.name = name.strip()
        role.save(update_fields=["name"])

    if description is not None and description != profile.description:
        changes["description"] = [profile.description, description]
        profile.description = description
        profile.save(update_fields=["description"])

    if permissions is not None:
        perms = resolve_permissions(permissions)
        new = permission_codes(perms)
        if new != current:
            _assert_actor_holds(actor, new)
            _assert_administrator_remains(role_perms={role.pk: new})
            role.permissions.set(perms)
            changes["permissions_added"] = sorted(new - current)
            changes["permissions_removed"] = sorted(current - new)

    if changes:
        record("role.updated", actor=actor, obj=role, changes=changes)
    return role


@transaction.atomic
def delete_role(actor, role):
    require_perm(actor, P.MANAGE_ROLES)
    profile = RoleProfile.objects.filter(group=role).first()
    if profile and profile.is_system:
        raise DomainError("System roles cannot be deleted.", code="system_role")
    if role.user_set.exists():
        raise DomainError("Remove this role from all officers before deleting it.", code="role_in_use")
    current = role_permissions([role])
    _assert_actor_holds(actor, current, "This role has permissions you do not hold, so you cannot delete it.")
    record("role.deleted", actor=actor, obj=role, changes={"permissions": [sorted(current), []]})
    role.delete()
