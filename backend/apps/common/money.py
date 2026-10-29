from decimal import ROUND_HALF_UP, Decimal

KOBO = Decimal("0.01")
ZERO = Decimal("0.00")


def to_money(value) -> Decimal:
    """Convert to Decimal and round half-up to kobo. Floats are rejected."""
    if isinstance(value, float):
        raise TypeError("Money values must not be floats; pass Decimal, int or str.")
    return Decimal(value).quantize(KOBO, rounding=ROUND_HALF_UP)
