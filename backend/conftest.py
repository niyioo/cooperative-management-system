import pytest
from rest_framework.test import APIClient

from tests.factories import DEFAULT_PASSWORD, MemberFactory, UserFactory, make_officer


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def password():
    return DEFAULT_PASSWORD


@pytest.fixture
def member(db):
    return MemberFactory()


@pytest.fixture
def super_admin(db):
    return make_officer("Super Administrator", email="admin@example.com")


@pytest.fixture
def officer_factory(db):
    return make_officer


@pytest.fixture
def user_factory(db):
    return UserFactory


@pytest.fixture
def member_factory(db):
    return MemberFactory


def auth(client, user):
    """Authenticate an APIClient with a real access token for `user`."""
    from apps.accounts.tokens import issue_tokens

    access, _, _ = issue_tokens(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def as_user(api):
    return lambda user: auth(api, user)


# ---------------------------------------------------------------------------
# Officers by role, and savings set-up shared by savings and ledger tests
# ---------------------------------------------------------------------------

@pytest.fixture
def treasurer(db):
    return make_officer("Treasurer")


@pytest.fixture
def accountant(db):
    return make_officer("Accountant")


@pytest.fixture
def secretary(db):
    return make_officer("Cooperative Secretary")


@pytest.fixture
def this_year():
    from django.utils import timezone

    return timezone.localdate().year


@pytest.fixture
def christmas(db):
    from apps.savings.models import SavingsProduct

    return SavingsProduct.objects.get(code="CHRISTMAS")


@pytest.fixture
def regular(db):
    from apps.savings.models import SavingsProduct

    return SavingsProduct.objects.get(code="REGULAR")


@pytest.fixture
def open_cycle(db, christmas, this_year, super_admin):
    """Christmas Savings for the current year, opened (accounts for active members)."""
    from apps.savings import services

    cycle = services.create_cycle(super_admin, product=christmas, year=this_year, expected_monthly_contribution=5000)
    services.open_cycle(super_admin, cycle)
    cycle.refresh_from_db()
    return cycle
