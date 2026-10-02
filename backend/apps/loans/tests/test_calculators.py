from datetime import date
from decimal import Decimal

import pytest

from apps.loans.calculators import build_schedule, month_end_after

D = Decimal


def schedule(principal, rate, term, *, basis="PER_ANNUM", method="FLAT", collection="AMORTISED", disbursed_on=date(2026, 1, 15)):
    return build_schedule(
        principal=D(principal), rate=D(rate), basis=basis, method=method, collection=collection,
        term_months=term, disbursed_on=disbursed_on,
    )


def test_month_end_after_handles_short_months_and_year_end():
    assert month_end_after(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert month_end_after(date(2027, 12, 5), 2) == date(2028, 2, 29)
    assert month_end_after(date(2026, 11, 30), 2) == date(2027, 1, 31)


def test_flat_per_annum():
    s = schedule("120000", "12", 12)
    assert s.total_interest == D("14400.00")
    assert {i.principal for i in s.instalments} == {D("10000.00")}
    assert {i.interest for i in s.instalments} == {D("1200.00")}
    assert s.total_payable == D("134400.00")
    assert s.first_due_date == date(2026, 2, 28)
    assert s.maturity_date == date(2027, 1, 31)


def test_flat_per_loan_and_per_month():
    assert schedule("100000", "7", 10, basis="PER_LOAN").total_interest == D("7000.00")
    assert schedule("100000", "1.5", 6, basis="PER_MONTH").total_interest == D("9000.00")


def test_rounding_goes_to_the_last_instalment():
    s = schedule("100000", "0", 3)
    assert [i.principal for i in s.instalments] == [D("33333.33"), D("33333.33"), D("33333.34")]
    assert sum(i.principal for i in s.instalments) == D("100000.00")


def test_reducing_balance_matches_standard_amortisation():
    s = schedule("100000", "12", 12, method="REDUCING_BALANCE")  # 1% a month
    assert s.monthly_payment == D("8884.88")
    assert s.instalments[0].interest == D("1000.00")
    assert sum(i.principal for i in s.instalments) == D("100000.00")
    assert s.total_interest == sum(i.interest for i in s.instalments)
    assert D("6618") < s.total_interest < D("6619")


def test_reducing_balance_at_zero_rate():
    s = schedule("1200", "0", 12, method="REDUCING_BALANCE")
    assert s.total_interest == D("0.00")
    assert {i.principal for i in s.instalments} == {D("100.00")}


def test_upfront_interest_leaves_principal_only_instalments():
    s = schedule("120000", "12", 12, collection="UPFRONT")
    assert s.total_interest == D("14400.00")
    assert {i.interest for i in s.instalments} == {D("0.00")}
    assert s.total_payable == D("120000.00")


def test_reducing_balance_rejects_a_whole_term_rate():
    with pytest.raises(ValueError):
        schedule("100000", "10", 12, basis="PER_LOAN", method="REDUCING_BALANCE")
