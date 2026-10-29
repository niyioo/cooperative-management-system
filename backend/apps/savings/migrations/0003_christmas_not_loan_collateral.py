"""
Christmas Savings is paid out every year, so by default it should not count
as security for loans. Officers can change this on the product.
"""
from django.db import migrations


def update(apps, schema_editor):
    SavingsProduct = apps.get_model("savings", "SavingsProduct")
    SavingsProduct.objects.filter(code="CHRISTMAS").update(counts_toward_loan_eligibility=False)


class Migration(migrations.Migration):
    dependencies = [("savings", "0002_seed_emdi_products")]

    operations = [migrations.RunPython(update, migrations.RunPython.noop)]
