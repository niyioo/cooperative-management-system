"""
Loan arithmetic. Pure functions with no database access, so they are simple to
unit-test and reuse (eligibility previews, disbursement, member portal quotes).

All money is Decimal rounded half-up to kobo. Instalments fall due on the last
day of each month, starting the month after disbursement, which lines up with
monthly payroll deductions.
"""
import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import InterestCollection, InterestMethod, InterestRateBasis

KOBO = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    return Decimal(value).quantize(KOBO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Instalment:
    number: int
    due_date: date
    principal: Decimal
    interest: Decimal

    @property
    def total(self):
        return self.principal + self.interest


@dataclass(frozen=True)
class Schedule:
    instalments: list
    total_interest: Decimal

    @property
    def total_payable(self):
        return sum((i.total for i in self.instalments), ZERO)

    @property
    def monthly_payment(self):
        """The regular instalment (the first; the last may differ by rounding)."""
        return self.instalments[0].total if self.instalments else ZERO

    @property
    def first_due_date(self):
        return self.instalments[0].due_date

    @property
    def maturity_date(self):
        return self.instalments[-1].due_date


def month_end_after(start, months):
    """Last day of the month `months` after `start` (months >= 1)."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def monthly_rate(rate, basis):
    """Periodic (monthly) rate as a fraction, for reducing-balance schedules."""
    rate = Decimal(rate) / 100
    if basis == InterestRateBasis.PER_ANNUM:
        return rate / 12
    if basis == InterestRateBasis.PER_MONTH:
        return rate
    raise ValueError("A reducing-balance loan needs a per-annum or per-month rate.")


def flat_interest(principal, rate, basis, term_months):
    rate = Decimal(rate) / 100
    if basis == InterestRateBasis.PER_ANNUM:
        return money(principal * rate * term_months / 12)
    if basis == InterestRateBasis.PER_MONTH:
        return money(principal * rate * term_months)
    return money(principal * rate)  # PER_LOAN


def _split_evenly(total, parts):
    """Split `total` into `parts` kobo-exact amounts; the last part absorbs rounding."""
    each = money(total / parts)
    return [each] * (parts - 1) + [total - each * (parts - 1)]


def build_schedule(*, principal, rate, basis, method, collection, term_months, disbursed_on):
    principal = money(principal)
    if principal <= 0 or term_months < 1:
        raise ValueError("Principal and term must be positive.")
    due_dates = [month_end_after(disbursed_on, n) for n in range(1, term_months + 1)]

    if method == InterestMethod.FLAT:
        total_interest = flat_interest(principal, rate, basis, term_months)
        principals = _split_evenly(principal, term_months)
        interests = _split_evenly(total_interest, term_months)
    else:
        r = monthly_rate(rate, basis)
        principals, interests, balance = [], [], principal
        if r == 0:
            principals = _split_evenly(principal, term_months)
            interests = [ZERO] * term_months
        else:
            payment = principal * r / (1 - (1 + r) ** -term_months)
            for n in range(term_months):
                interest = money(balance * r)
                part = balance if n == term_months - 1 else money(payment - interest)
                principals.append(part)
                interests.append(interest)
                balance -= part
        total_interest = sum(interests, ZERO)

    if collection == InterestCollection.UPFRONT:
        # Interest is deducted from the disbursement, so instalments repay principal only.
        interests = [ZERO] * term_months

    instalments = [
        Instalment(number=n + 1, due_date=due_dates[n], principal=principals[n], interest=interests[n])
        for n in range(term_months)
    ]
    return Schedule(instalments=instalments, total_interest=total_interest)


def schedule_for_product(product, amount, term_months, disbursed_on):
    return build_schedule(
        principal=amount,
        rate=product.interest_rate,
        basis=product.interest_rate_basis,
        method=product.interest_method,
        collection=product.interest_collection,
        term_months=term_months,
        disbursed_on=disbursed_on,
    )
