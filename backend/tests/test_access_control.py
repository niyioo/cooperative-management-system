"""
Access-control sweep over every API endpoint (BR-14, BR-16).

Rather than trusting each view's tests, this walks the whole URL map and
checks three kinds of caller against every route and method:

  * anonymous            -> 401 everywhere under /admin/ and /me/
  * a member (no roles)  -> 403 everywhere under /admin/
  * an officer, no roles -> 403 under /admin/ except the deliberately open
                            reference endpoints listed in ANY_OFFICER below,
                            and 403 everywhere under /me/ (no member profile)

A new endpoint that forgets its permission_map, or maps an action to "any
officer" by accident, fails here.
"""
import re
import uuid

import pytest
from drf_spectacular.generators import EndpointEnumerator

from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db

# Officer endpoints any signed-in officer may use, by design: reference data
# that officer forms need, the dashboard (its sections follow permissions),
# reading cooperative settings, and rejecting a pending entry (the service
# lets the creator cancel their own entry and checks everyone else).
ANY_OFFICER = {
    ("GET", "/api/v1/admin/dashboard/"),
    ("GET", "/api/v1/admin/settings/"),
    ("GET", "/api/v1/admin/departments/"),
    ("GET", "/api/v1/admin/departments/{id}/"),
    ("GET", "/api/v1/admin/savings/products/"),
    ("GET", "/api/v1/admin/savings/products/{id}/"),
    ("GET", "/api/v1/admin/loans/products/"),
    ("GET", "/api/v1/admin/loans/products/{id}/"),
    ("GET", "/api/v1/admin/loans/products/{id}/quote/"),
    ("GET", "/api/v1/admin/investments/products/"),
    ("GET", "/api/v1/admin/investments/products/{id}/"),
    ("POST", "/api/v1/admin/transactions/{id}/reject/"),
}


def endpoints(prefix):
    seen = set()
    for path, _regex, method, _callback in EndpointEnumerator().get_api_endpoints():
        path = path.replace("{pk}", "{id}")
        if path.startswith(prefix) and (path, method) not in seen:
            seen.add((path, method))
            yield method, path


def concrete(path):
    """Fill path parameters: report keys get a real report, everything else a random UUID."""
    path = path.replace("{key}", "members")
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)


def call(client, method, path):
    url = concrete(path)
    return getattr(client, method.lower())(url, {}, format="json") if method != "GET" else client.get(url)


ADMIN = sorted(endpoints("/api/v1/admin/"))
ME = sorted(endpoints("/api/v1/me/"))


def test_the_sweep_sees_the_whole_api():
    assert len(ADMIN) > 100 and len(ME) > 25
    stale = ANY_OFFICER - set(ADMIN)
    assert not stale, f"ANY_OFFICER lists endpoints that no longer exist: {stale}"


@pytest.mark.parametrize("method,path", ADMIN + ME)
def test_anonymous_callers_are_refused(api, method, path):
    assert call(api, method, path).status_code == 401


@pytest.mark.parametrize("method,path", ADMIN)
def test_members_cannot_use_officer_endpoints(as_user, method, path):
    member = MemberFactory()
    assert call(as_user(member.user), method, path).status_code == 403


@pytest.mark.parametrize("method,path", ADMIN)
def test_officers_need_a_permission_for_each_officer_endpoint(as_user, method, path):
    officer = UserFactory(is_staff_officer=True)  # an officer with no roles at all
    status = call(as_user(officer), method, path).status_code
    if (method, path) in ANY_OFFICER:
        assert status not in (401, 403), f"{method} {path} should be open to any officer"
    else:
        assert status == 403, f"{method} {path} returned {status} to an officer with no permissions"


@pytest.mark.parametrize("method,path", ME)
def test_officers_without_a_membership_cannot_use_member_endpoints(as_user, method, path):
    officer = UserFactory(is_staff_officer=True)
    assert call(as_user(officer), method, path).status_code == 403
