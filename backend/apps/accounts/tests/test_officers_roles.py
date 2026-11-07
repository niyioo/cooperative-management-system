import pytest
from django.contrib.auth.models import Group
from django.core import mail

from apps.accounts import services
from apps.accounts.models import User
from apps.accounts.perms import ALL_PERMISSIONS, P
from apps.audit.models import AuditLog
from tests.factories import DEFAULT_PASSWORD, make_officer

pytestmark = pytest.mark.django_db

OFFICERS = "/api/v1/admin/officers/"
ROLES = "/api/v1/admin/roles/"


def role(name):
    return Group.objects.get(name=name)


def code(response):
    return response.data["error"]["code"]


@pytest.fixture
def officer_manager(super_admin):
    """An officer who may manage officers but holds few other permissions."""
    services.create_role(super_admin, name="Officer Manager", permissions=[P.MANAGE_OFFICERS, P.VIEW_MEMBER])
    return make_officer("Officer Manager", email="manager@example.com")


class TestOfficers:
    def test_create_officer_sends_activation(self, as_user, super_admin, django_capture_on_commit_callbacks):
        with django_capture_on_commit_callbacks(execute=True):
            response = as_user(super_admin).post(
                OFFICERS,
                {"email": "Treasurer@Example.com", "first_name": "Tola", "last_name": "Ade", "roles": [role("Treasurer").pk]},
                format="json",
            )
        assert response.status_code == 201
        assert response.data["account_created"] is True
        assert response.data["is_activated"] is False
        assert [r["name"] for r in response.data["roles"]] == ["Treasurer"]
        user = User.objects.get(email="treasurer@example.com")
        assert user.is_staff_officer and not user.has_usable_password()
        assert len(mail.outbox) == 1 and "Activate" in mail.outbox[0].subject
        assert AuditLog.objects.filter(action="officer.access_granted", object_id=str(user.pk)).exists()

    def test_existing_member_is_promoted_not_duplicated(self, as_user, super_admin, member):
        response = as_user(super_admin).post(
            OFFICERS,
            {"email": member.user.email, "first_name": "x", "last_name": "y", "roles": [role("Accountant").pk]},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["account_created"] is False
        assert response.data["membership_number"] == member.membership_number
        assert User.objects.filter(email=member.user.email).count() == 1

    def test_cannot_grant_permissions_you_do_not_hold(self, as_user, officer_manager):
        response = as_user(officer_manager).post(
            OFFICERS,
            {"email": "new@example.com", "first_name": "N", "last_name": "O", "roles": [role("Treasurer").pk]},
            format="json",
        )
        assert response.status_code == 400
        assert code(response) == "privilege_escalation"

    def test_cannot_manage_officer_with_more_permissions(self, as_user, officer_manager, super_admin):
        response = as_user(officer_manager).post(f"{OFFICERS}{super_admin.pk}/revoke/", {}, format="json")
        assert response.status_code == 400
        assert code(response) == "privilege_escalation"

    def test_cannot_change_own_roles(self, as_user, super_admin):
        response = as_user(super_admin).put(
            f"{OFFICERS}{super_admin.pk}/roles/", {"roles": [role("Auditor").pk]}, format="json"
        )
        assert response.status_code == 400
        assert code(response) == "self_action"

    def test_change_roles(self, as_user, super_admin):
        treasurer = make_officer("Treasurer")
        response = as_user(super_admin).put(
            f"{OFFICERS}{treasurer.pk}/roles/", {"roles": [role("Accountant").pk, role("Loan Officer").pk]}, format="json"
        )
        assert response.status_code == 200
        assert sorted(r["name"] for r in response.data["roles"]) == ["Accountant", "Loan Officer"]
        log = AuditLog.objects.get(action="officer.roles_changed")
        assert log.changes == {"roles": [["Treasurer"], ["Accountant", "Loan Officer"]]}

    def test_revoke_keeps_the_account_and_member_profile(self, as_user, super_admin, member):
        member.user.is_staff_officer = True
        member.user.save()
        member.user.groups.add(role("Accountant"))

        response = as_user(super_admin).post(f"{OFFICERS}{member.user.pk}/revoke/", {"reason": "Tenure ended"}, format="json")
        assert response.status_code == 204
        member.user.refresh_from_db()
        assert member.user.is_active and not member.user.is_staff_officer
        assert member.user.groups.count() == 0

    def test_last_administrator_cannot_be_removed(self, super_admin):
        other_admin = make_officer("Super Administrator")
        services.revoke_officer_access(super_admin, other_admin)  # fine: super_admin remains
        with pytest.raises(services.DomainError) as exc:
            services.update_role(
                super_admin,
                role("Super Administrator"),
                permissions=sorted(ALL_PERMISSIONS - {P.MANAGE_ROLES}),
            )
        assert exc.value.code == "last_administrator"

    def test_temporary_password_forces_change(self, api, as_user, super_admin):
        treasurer = make_officer("Treasurer")
        response = as_user(super_admin).post(f"{OFFICERS}{treasurer.pk}/temporary-password/")
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"
        temp = response.data["temporary_password"]

        api.credentials()
        login = api.post("/api/v1/auth/login/", {"identifier": treasurer.email, "password": temp}, format="json")
        assert login.data["user"]["must_change_password"] is True
        assert api.post("/api/v1/auth/login/", {"identifier": treasurer.email, "password": DEFAULT_PASSWORD}, format="json").status_code == 401
        assert temp not in str(list(AuditLog.objects.values_list("metadata", "changes")))

    def test_list_officers(self, as_user, super_admin):
        make_officer("Auditor")
        response = as_user(super_admin).get(OFFICERS)
        assert response.status_code == 200
        assert response.data["count"] == 2


class TestRoles:
    def test_create_custom_role(self, as_user, super_admin):
        response = as_user(super_admin).post(
            ROLES,
            {"name": "Welfare Officer", "description": "Welfare desk", "permissions": [P.VIEW_MEMBER, P.VIEW_SAVINGS]},
            format="json",
        )
        assert response.status_code == 201
        assert response.data["permissions"] == sorted([P.VIEW_MEMBER, P.VIEW_SAVINGS])
        assert response.data["is_system"] is False
        assert response.data["officer_count"] == 0

    def test_unknown_permission_rejected(self, as_user, super_admin):
        response = as_user(super_admin).post(ROLES, {"name": "Bad", "permissions": ["loans.fly"]}, format="json")
        assert response.status_code == 400
        assert code(response) == "unknown_permission"

    def test_duplicate_name_rejected(self, as_user, super_admin):
        response = as_user(super_admin).post(ROLES, {"name": "treasurer", "permissions": []}, format="json")
        assert code(response) == "duplicate_name"

    def test_system_roles_cannot_be_deleted_or_renamed(self, as_user, super_admin):
        client = as_user(super_admin)
        treasurer = role("Treasurer")
        assert code(client.delete(f"{ROLES}{treasurer.pk}/")) == "system_role"
        assert code(client.patch(f"{ROLES}{treasurer.pk}/", {"name": "Bursar"}, format="json")) == "system_role"

    def test_role_in_use_cannot_be_deleted(self, as_user, super_admin):
        custom = services.create_role(super_admin, name="Desk", permissions=[P.VIEW_MEMBER])
        officer = make_officer("Treasurer")
        officer.groups.add(custom)
        assert code(as_user(super_admin).delete(f"{ROLES}{custom.pk}/")) == "role_in_use"

    def test_delete_unused_custom_role(self, as_user, super_admin):
        custom = services.create_role(super_admin, name="Temp", permissions=[])
        assert as_user(super_admin).delete(f"{ROLES}{custom.pk}/").status_code == 204
        assert AuditLog.objects.filter(action="role.deleted").exists()

    def test_update_permissions_is_audited(self, as_user, super_admin):
        custom = services.create_role(super_admin, name="Desk", permissions=[P.VIEW_MEMBER])
        response = as_user(super_admin).patch(
            f"{ROLES}{custom.pk}/", {"permissions": [P.VIEW_SAVINGS]}, format="json"
        )
        assert response.status_code == 200
        log = AuditLog.objects.get(action="role.updated")
        assert log.changes == {"permissions_added": [P.VIEW_SAVINGS], "permissions_removed": [P.VIEW_MEMBER]}

    def test_officer_manager_can_list_roles_but_not_edit(self, as_user, officer_manager):
        client = as_user(officer_manager)
        assert client.get(ROLES).status_code == 200
        assert client.post(ROLES, {"name": "X", "permissions": []}, format="json").status_code == 403

    def test_permission_catalogue(self, as_user, super_admin):
        response = as_user(super_admin).get("/api/v1/admin/permissions/")
        assert response.status_code == 200
        assert response.data[0]["module"] == "members"
        assert sum(len(m["permissions"]) for m in response.data) == len(ALL_PERMISSIONS)
