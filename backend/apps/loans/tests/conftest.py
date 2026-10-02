import datetime
from decimal import Decimal

import pytest

from apps.loans import services
from apps.loans.models import LoanProduct
from tests.factories import MemberFactory, accept_guarantees, add_guarantors, make_officer

from .helpers import give_savings


@pytest.fixture
def loan_officer(db):
    return make_officer("Loan Officer")


@pytest.fixture
def chairman(db):
    return make_officer("Cooperative Chairman")


@pytest.fixture
def product(db):
    return LoanProduct.objects.create(
        name="Regular Loan",
        code="REG",
        interest_rate=Decimal("12"),
        interest_rate_basis="PER_ANNUM",
        interest_method="FLAT",
        interest_collection="AMORTISED",
        min_amount=Decimal("10000"),
        max_amount=Decimal("1000000"),
        max_savings_multiple=Decimal("2"),
        min_term_months=1,
        max_term_months=24,
        min_membership_months=6,
    )


@pytest.fixture
def borrower(db):
    member = MemberFactory(date_joined=datetime.date(2020, 1, 1), last_name="Borrower")
    give_savings(member, "100000")
    return member


@pytest.fixture
def approved(borrower, product, loan_officer, chairman):
    """An application for ₦120,000 over 12 months, reviewed and approved."""

    def make(amount="120000", term=12, member=None):
        application = services.create_application(
            loan_officer, member=member or borrower, product=product,
            amount_requested=Decimal(amount), term_months=term, purpose="School fees",
        )
        add_guarantors(loan_officer, application)
        services.submit_application(loan_officer, application)
        accept_guarantees(application)
        services.start_review(loan_officer, application)
        return services.approve_application(chairman, application)

    return make
