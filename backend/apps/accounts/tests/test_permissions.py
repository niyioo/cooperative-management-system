import pytest
from django.contrib.auth.models import Group, Permission
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.accounts.permissions import OfficerAPIMixin, assert_not_self
from apps.accounts.perms import ALL_PERMISSIONS, PERMISSION_APPS, P
from apps.common.exceptions import DomainError
from tests.factories import make_officer

pytestmark = pytest.mark.django_db

ROLES_URL = "/api/v1/admin/roles/"
OFFICERS_URL = "/api/v1/admin/officers/"


def perms_of(role_name):
    group = Group.objects.get(name=role_name)
    return {f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.select_related("content_type")}


class TestCatalogueAndSeededRoles:
    def test_catalogue_constants_match_declared_permissions(self):
        declared = {
            f"{a}.{c}"
            for a, c in Permission.objects.filter(content_type__app_label__in=PERMISSION_APPS).values_list(
                "content_type__app_label", "codename"
            )
        }
        assert declared == ALL_PERMISSIONS

    def test_default_roles_exist_and_are_system_roles(self):
        expected = {
            "Super Administrator",
            "Cooperative Chairman",
            "Cooperative Secretary",
            "Treasurer",
            "Accountant",
            "Loan Officer",
            "Investment Officer",
            "Auditor",
        }
        assert set(Group.objects.values_list("name", flat=True)) >= expected
        assert all(Group.objects.get(name=n).profile.is_system for n in expected)

    def test_super_administrator_has_everything(self):
        assert perms_of("Super Administrator") == ALL_PERMISSIONS

    def test_auditor_is_read_only(self):
        for code in perms_of("Auditor"):
            codename = code.split(".")[1]
            assert codename.startswith("view_") or code == P.EXPORT_REPORTS, code

    def test_separation_of_duties(self):
        chairman, treasurer, accountant = perms_of("Cooperative Chairman"), perms_of("Treasurer"), perms_of("Accountant")
        assert P.APPROVE_LOAN_APPLICATION in chairman and P.DISBURSE_LOAN not in chairman
        assert P.DISBURSE_LOAN in treasurer
        # Accountants prepare entries; someone else approves them.
        assert P.POST_ADJUSTMENT in accountant
        assert P.APPROVE_TRANSACTION not in accountant and P.APPROVE_BATCH not in accountant
        # Dividends: calculated by one role, approved by another.
        assert P.CALCULATE_DIVIDENDS in accountant and P.APPROVE_DIVIDENDS not in accountant
        assert P.APPROVE_DIVIDENDS in chairman and P.CALCULATE_DIVIDENDS not in chairman
        # Closures: reviewed, approved and executed by different roles.
        assert P.REVIEW_CLOSURE_REQUEST in perms_of("Cooperative Secretary")
        assert P.APPROVE_CLOSURE_REQUEST in chairman
        assert P.EXECUTE_ACCOUNT_CLOSURE in treasurer


class TestPortalAccess:
    def test_anonymous_gets_401(self, api):
        assert api.get(ROLES_URL).status_code == 401

    def test_member_cannot_reach_officer_api(self, as_user, member):
        assert as_user(member.user).get(ROLES_URL).status_code == 403

    def test_officer_without_permission_gets_403(self, as_user):
        loan_officer = make_officer("Loan Officer")
        assert as_user(loan_officer).get(OFFICERS_URL).status_code == 403

    def test_forced_password_change_blocks_officer_api(self, as_user, super_admin):
        super_admin.must_change_password = True
        super_admin.save()
        client = as_user(super_admin)
        response = client.get(ROLES_URL)
        assert response.status_code == 403
        assert response.data["error"]["code"] == "password_change_required"
        assert client.get("/api/v1/auth/me/").status_code == 200

    def test_unmapped_actions_are_denied(self, super_admin):
        class Unmapped(OfficerAPIMixin, APIView):
            permission_map = {"get": ()}

            def get(self, request):
                return None

            def post(self, request):  # not in permission_map
                return None

        request = APIRequestFactory().post("/x/")
        force_authenticate(request, user=super_admin)
        assert Unmapped.as_view()(request).status_code == 403


class TestSelfDealingGuard:
    def test_officer_cannot_act_on_own_member_record(self, member):
        with pytest.raises(DomainError) as exc:
            assert_not_self(member.user, member, "approve a loan for")
        assert exc.value.code == "self_dealing"

    def test_other_members_are_fine(self, member, super_admin):
        assert_not_self(super_admin, member)
