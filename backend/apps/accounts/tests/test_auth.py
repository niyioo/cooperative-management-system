import re

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache

from apps.accounts.throttles import LoginRateThrottle
from apps.accounts.tokens import activation_token, encode_uid
from apps.audit.models import AuditLog
from tests.factories import MemberFactory, UserFactory, make_officer

pytestmark = pytest.mark.django_db

LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/token/refresh/"
LOGOUT = "/api/v1/auth/logout/"
ME = "/api/v1/auth/me/"
CHANGE = "/api/v1/auth/password/change/"
RESET = "/api/v1/auth/password/reset/"
RESET_CONFIRM = "/api/v1/auth/password/reset/confirm/"
ACTIVATE = "/api/v1/auth/activate/"
COOKIE = settings.REFRESH_COOKIE["NAME"]
XHR = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
NEW_PASSWORD = "Brand-New-Secret-42"


def login(api, identifier, password):
    return api.post(LOGIN, {"identifier": identifier, "password": password}, format="json")


def error_code(response):
    return response.data["error"]["code"]


class TestLogin:
    def test_member_logs_in_with_email(self, api, member, password):
        response = login(api, member.user.email.upper(), password)

        assert response.status_code == 200
        assert response.data["access"]
        assert "refresh" not in response.data  # never exposed to JavaScript
        assert response.data["user"]["member"]["membership_number"] == member.membership_number
        assert response.data["user"]["portals"] == ["member"]
        cookie = response.cookies[COOKIE]
        assert cookie["httponly"]
        assert cookie["path"] == "/api/v1/auth/"
        assert AuditLog.objects.filter(action="auth.login_succeeded", actor=member.user).exists()

    def test_member_logs_in_with_membership_number(self, api, member, password):
        response = login(api, member.membership_number.lower(), password)
        assert response.status_code == 200

    def test_wrong_password_gets_generic_error(self, api, member):
        response = login(api, member.user.email, "not-the-password")
        assert response.status_code == 401
        assert error_code(response) == "invalid_credentials"
        assert AuditLog.objects.filter(action="auth.login_failed").exists()

    def test_unknown_account_gets_identical_error(self, api, member):
        unknown = login(api, "nobody@example.com", "whatever")
        wrong = login(api, member.user.email, "whatever")
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.data == wrong.data

    def test_inactive_user_rejected(self, api, member, password):
        member.user.is_active = False
        member.user.save()
        assert login(api, member.user.email, password).status_code == 401

    def test_user_without_any_portal_rejected(self, api, password):
        user = UserFactory()  # neither officer nor member
        assert login(api, user.email, password).status_code == 401

    def test_officer_payload_lists_roles_and_permissions(self, api, password):
        officer = make_officer("Treasurer")
        user = login(api, officer.email, password).data["user"]
        assert user["is_officer"] is True
        assert user["roles"] == ["Treasurer"]
        assert "loans.disburse_loan" in user["permissions"]
        assert "accounts.manage_roles" not in user["permissions"]
        assert user["portals"] == ["officer"]

    def test_officer_who_is_also_a_member_gets_both_portals(self, api, member, password):
        member.user.is_staff_officer = True
        member.user.save()
        member.user.groups.add(Group.objects.get(name="Treasurer"))
        assert login(api, member.user.email, password).data["user"]["portals"] == ["officer", "member"]

    def test_repeated_attempts_are_throttled(self, api, member, monkeypatch):
        cache.clear()
        monkeypatch.setattr(LoginRateThrottle, "THROTTLE_RATES", {"login": "2/min"})
        login(api, member.user.email, "bad-1")
        login(api, member.user.email, "bad-2")
        assert login(api, member.user.email, "bad-3").status_code == 429
        cache.clear()

    def test_missing_fields_return_validation_envelope(self, api):
        response = api.post(LOGIN, {}, format="json")
        assert response.status_code == 400
        assert error_code(response) == "validation_error"
        assert set(response.data["error"]["fields"]) == {"identifier", "password"}


class TestRefreshAndLogout:
    def test_refresh_requires_xhr_header(self, api, member, password):
        login(api, member.user.email, password)
        response = api.post(REFRESH)
        assert response.status_code == 403
        assert error_code(response) == "csrf_header_missing"

    def test_refresh_rotates_and_old_token_cannot_be_reused(self, api, member, password):
        login(api, member.user.email, password)
        old = api.cookies[COOKIE].value

        response = api.post(REFRESH, **XHR)
        assert response.status_code == 200
        assert response.data["access"]
        assert api.cookies[COOKIE].value != old

        api.cookies[COOKIE] = old
        reused = api.post(REFRESH, **XHR)
        assert reused.status_code == 401
        assert error_code(reused) == "session_expired"

    def test_refresh_without_cookie(self, api):
        response = api.post(REFRESH, **XHR)
        assert response.status_code == 401

    def test_refresh_fails_once_user_is_deactivated(self, api, member, password):
        login(api, member.user.email, password)
        member.user.is_active = False
        member.user.save()
        response = api.post(REFRESH, **XHR)
        assert response.status_code == 401
        assert response.cookies[COOKIE]["max-age"] == 0  # cookie cleared

    def test_logout_ends_the_session(self, api, member, password):
        login(api, member.user.email, password)
        assert api.post(LOGOUT, **XHR).status_code == 204
        assert api.post(REFRESH, **XHR).status_code == 401
        assert AuditLog.objects.filter(action="auth.logout").exists()


class TestMe:
    def test_requires_authentication(self, api):
        response = api.get(ME)
        assert response.status_code == 401
        assert error_code(response) == "not_authenticated"

    def test_returns_current_user(self, as_user, member):
        response = as_user(member.user).get(ME)
        assert response.status_code == 200
        assert response.data["email"] == member.user.email


class TestPasswordChange:
    def test_change_revokes_existing_tokens_and_returns_a_new_session(self, api, member, password):
        old_access = login(api, member.user.email, password).data["access"]
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")

        response = api.post(CHANGE, {"current_password": password, "new_password": NEW_PASSWORD}, format="json")
        assert response.status_code == 200
        new_access = response.data["access"]

        assert api.get(ME).status_code == 401  # old token revoked
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        assert api.get(ME).status_code == 200
        api.credentials()
        assert login(api, member.user.email, NEW_PASSWORD).status_code == 200

    def test_wrong_current_password(self, as_user, member):
        response = as_user(member.user).post(
            CHANGE, {"current_password": "wrong", "new_password": NEW_PASSWORD}, format="json"
        )
        assert response.status_code == 400
        assert error_code(response) == "invalid_password"

    def test_weak_new_password(self, as_user, member, password):
        response = as_user(member.user).post(CHANGE, {"current_password": password, "new_password": "12345678"}, format="json")
        assert response.status_code == 400
        assert error_code(response) == "weak_password"
        assert "new_password" in response.data["error"]["fields"]

    def test_clears_forced_change_flag(self, as_user, member, password):
        member.user.must_change_password = True
        member.user.save()
        as_user(member.user).post(CHANGE, {"current_password": password, "new_password": NEW_PASSWORD}, format="json")
        member.user.refresh_from_db()
        assert member.user.must_change_password is False


def _link_parts(body):
    match = re.search(r"uid=([^&\s]+)&token=([^\s]+)", body)
    return match.group(1), match.group(2)


class TestPasswordReset:
    def test_unknown_email_gets_the_same_response(self, api):
        response = api.post(RESET, {"email": "nobody@example.com"}, format="json")
        assert response.status_code == 202
        assert len(mail.outbox) == 0

    def test_full_reset_flow_and_link_is_single_use(self, api, member):
        assert api.post(RESET, {"email": member.user.email}, format="json").status_code == 202
        assert len(mail.outbox) == 1
        uid, token = _link_parts(mail.outbox[0].body)

        payload = {"uid": uid, "token": token, "new_password": NEW_PASSWORD}
        assert api.post(RESET_CONFIRM, payload, format="json").status_code == 200
        assert login(api, member.user.email, NEW_PASSWORD).status_code == 200

        reused = api.post(RESET_CONFIRM, {**payload, "new_password": "Another-Secret-99"}, format="json")
        assert reused.status_code == 400
        assert error_code(reused) == "invalid_token"

    def test_expired_link_is_rejected(self, api, member, settings):
        api.post(RESET, {"email": member.user.email}, format="json")
        uid, token = _link_parts(mail.outbox[0].body)
        settings.PASSWORD_RESET_TOKEN_TIMEOUT = -1
        response = api.post(RESET_CONFIRM, {"uid": uid, "token": token, "new_password": NEW_PASSWORD}, format="json")
        assert response.status_code == 400

    def test_unactivated_account_receives_activation_link_instead(self, api):
        user = UserFactory(password=None)
        MemberFactory(user=user)
        api.post(RESET, {"email": user.email}, format="json")
        assert "Activate" in mail.outbox[0].subject


class TestActivation:
    def _payload(self, user, password=NEW_PASSWORD):
        return {"uid": encode_uid(user), "token": activation_token.make_token(user), "new_password": password}

    def test_activation_sets_password_once(self, api):
        user = UserFactory(password=None)
        MemberFactory(user=user)
        payload = self._payload(user)

        assert api.post(ACTIVATE, payload, format="json").status_code == 200
        assert login(api, user.email, NEW_PASSWORD).status_code == 200
        assert api.post(ACTIVATE, payload, format="json").status_code == 400

    def test_already_activated_account_cannot_use_activation(self, api, member):
        response = api.post(ACTIVATE, self._payload(member.user), format="json")
        assert response.status_code == 400
        assert error_code(response) == "invalid_token"
