"""
Balance calculations. Balances are never stored (ARCHITECTURE.md D1): they are
the signed sum of posted ledger entries.

    savings / investment balance = credits - debits  = net
    loan outstanding            = debits - credits  = -net
"""
from decimal import Decimal

from django.db.models import Case, F, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.common.fields import MoneyField

from .choices import EntrySide
from .models import Transaction

ZERO = Decimal("0.00")

SIGNED_AMOUNT = Case(
    When(entry_side=EntrySide.CREDIT, then=F("amount")),
    default=-F("amount"),
    output_field=MoneyField(),
)


def net_by(field, **filters):
    """{account_id: net} for posted entries grouped by an account field, e.g. net_by("savings_account", member=m)."""
    rows = (
        Transaction.objects.posted()
        .filter(**filters, **{f"{field}__isnull": False})
        .values(field)
        .annotate(net=Sum(SIGNED_AMOUNT))
    )
    return {row[field]: row["net"] or ZERO for row in rows}


def member_transactions(member):
    return (
        Transaction.objects.filter(member=member)
        .select_related(
            "savings_account__product",
            "savings_account__cycle",
            "loan",
            "investment_account__product",
            "created_by",
            "approved_by",
        )
        .order_by("-value_date", "-created_at")
    )


def with_balance(queryset, field):
    """
    Annotate account rows with `balance` (net of posted entries) in one query,
    e.g. with_balance(SavingsAccount.objects.all(), "savings_account").
    """
    net = (
        Transaction.objects.posted()
        .filter(**{field: OuterRef("pk")})
        .values(field)
        .annotate(net=Sum(SIGNED_AMOUNT))
        .values("net")
    )
    return queryset.annotate(balance=Coalesce(Subquery(net, output_field=MoneyField()), Value(ZERO), output_field=MoneyField()))
