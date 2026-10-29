"""
EMDI's two savings products (ARCHITECTURE.md BR-02/BR-03). Created only if
missing; officers adjust amounts and rules afterwards. Expected contributions
start at zero because the cooperative sets them.
"""
from django.db import migrations

PRODUCTS = [
    {
        "code": "CHRISTMAS",
        "name": "Christmas Savings",
        "description": "Yearly savings collected from January to October and paid out before Christmas.",
        "kind": "CYCLE",
        "cycle_start_month": 1,
        "cycle_end_month": 10,
        "payout_month": 11,
        "display_order": 1,
    },
    {
        "code": "REGULAR",
        "name": "Regular Savings",
        "description": "Ordinary cooperative savings.",
        "kind": "REGULAR",
        "is_mandatory": True,
        "display_order": 2,
    },
]


def seed(apps, schema_editor):
    SavingsProduct = apps.get_model("savings", "SavingsProduct")
    for product in PRODUCTS:
        SavingsProduct.objects.get_or_create(code=product["code"], defaults=product)


class Migration(migrations.Migration):
    dependencies = [
        ("savings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
