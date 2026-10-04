"""Rate limits on the whole API and on password changes, no caching of API responses, and the monthly contribution ceiling."""
from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.accounts.throttles import APIAnonRateThrottle, APIUserRateThrottle, PasswordChangeRateThrottle
from apps.savings import services
from apps.savings.models import SavingsAccount, SavingsProduct

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fresh_counters():
    cache.clear()
    yield
    cache.clear()


class TestRateLimits:
    def test_signed_in_requests_are_limited_per_user(self, as_user, member, monkeypatch):
        monkeypatch.setattr(APIUserRateThrottle, "THROTTLE_RATES", {"user": "2/min"})
        client = as_user(member.user)
        assert client.get("/api/v1/me/dashboard/").status_code == 200
        assert client.get("/api/v1/me/savings/").status_code == 200
        response = client.get("/api/v1/me/dashboard/")
        assert response.status_code == 429
        assert response.data["error"]["code"] == "throttled"

    def test_signed_out_requests_are_limited_per_address(self, api, monkeypatch):
        monkeypatch.setattr(APIAnonRateThrottle, "THROTTLE_RATES", {"anon": "2/min"})
        refresh = "/api/v1/auth/token/refresh/"
        api.post(refresh, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        api.post(refresh, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert api.post(refresh, HTTP_X_REQUESTED_WITH="XMLHttpRequest").status_code == 429

    def test_health_checks_are_never_limited(self, api, monkeypatch):
        monkeypatch.setattr(APIAnonRateThrottle, "THROTTLE_RATES", {"anon": "1/min"})
        assert all(api.get("/api/v1/health/").status_code == 200 for _ in range(3))

    def test_guessing_the_current_password_is_limited(self, as_user, member, monkeypatch):
        monkeypatch.setattr(PasswordChangeRateThrottle, "THROTTLE_RATES", {"password_change": "2/min"})
        client = as_user(member.user)
        attempt = {"current_password": "wrong-guess-1", "new_password": "A-new-password-2026"}
        client.post("/api/v1/auth/password/change/", attempt, format="json")
        client.post("/api/v1/auth/password/change/", attempt, format="json")
        assert client.post("/api/v1/auth/password/change/", attempt, format="json").status_code == 429


class TestNoCaching:
    def test_login_response_with_the_access_token_is_never_stored(self, api, member, password):
        response = api.post("/api/v1/auth/login/", {"identifier": member.user.email, "password": password}, format="json")
        assert response.status_code == 200 and "access" in response.data
        assert response["Cache-Control"] == "no-store"
        assert response["Pragma"] == "no-cache"

    def test_financial_data_is_never_stored(self, as_user, member):
        assert as_user(member.user).get("/api/v1/me/savings/")["Cache-Control"] == "no-store"

    def test_refresh_token_is_only_in_an_httponly_cookie(self, api, member, password):
        response = api.post("/api/v1/auth/login/", {"identifier": member.user.email, "password": password}, format="json")
        assert "refresh" not in response.data
        cookie = next(iter(response.cookies.values()))
        assert cookie["httponly"] and cookie["path"] == "/api/v1/auth/"


class TestMonthlyContributionCeiling:
    @pytest.fixture
    def regular(self, db):
        product = SavingsProduct.objects.get(code="REGULAR")
        product.min_contribution = Decimal("5000")
        product.save()
        return product

    def test_regular_savings_has_a_default_ceiling(self, regular):
        assert regular.max_monthly_contribution == Decimal("1000000.00")

    def test_member_cannot_choose_more_than_the_maximum(self, as_user, member, regular):
        SavingsAccount.objects.get_or_create(member=member, product=regular, cycle=None)
        client = as_user(member.user)
        response = client.post("/api/v1/me/savings/monthly-contribution/", {"amount": "1000000.01"}, format="json")
        assert response.status_code == 400
        assert response.data["error"]["code"] == "above_maximum"
        assert client.get("/api/v1/me/savings/monthly-contribution/").data["maximum"] == "1000000.00"
        assert client.post("/api/v1/me/savings/monthly-contribution/", {"amount": "1000000"}, format="json").status_code == 200

    def test_maximum_cannot_be_below_the_minimum(self, super_admin, regular):
        from apps.common.exceptions import DomainError

        with pytest.raises(DomainError) as raised:
            services.update_product(super_admin, regular, max_monthly_contribution=Decimal("4000"))
        assert raised.value.code == "invalid_maximum"

    def test_blank_maximum_means_no_limit(self, as_user, member, super_admin, regular):
        services.update_product(super_admin, regular, max_monthly_contribution=None)
        SavingsAccount.objects.get_or_create(member=member, product=regular, cycle=None)
        response = as_user(member.user).post("/api/v1/me/savings/monthly-contribution/", {"amount": "5000000"}, format="json")
        assert response.status_code == 200
