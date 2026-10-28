"""
EMDI's third savings product (BR-37): Pre-retirement Savings, a voluntary continuous savings that members
add to from salary or by hand and draw when they retire. Paid out by an officer, with a second officer's
approval. Created only if missing; officers adjust it afterwards.
"""
from django.db import migrations

PRODUCT = {
    "code": "PRE_RETIREMENT",
    "name": "Pre-retirement Savings",
    "description": "Voluntary savings towards retirement, from salary or paid by hand; paid out on retirement.",
    "kind": "REGULAR",
    "is_mandatory": False,
    "allow_officer_withdrawal": True,
    "display_order": 3,
}


def seed(apps, schema_editor):
    apps.get_model("savings", "SavingsProduct").objects.get_or_create(code=PRODUCT["code"], defaults=PRODUCT)


class Migration(migrations.Migration):
    dependencies = [("savings", "0009_real_ledger_practices")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
