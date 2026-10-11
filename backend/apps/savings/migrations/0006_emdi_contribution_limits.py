from decimal import Decimal

from django.db import migrations


def set_emdi_limits(apps, schema_editor):
    """
    EMDI's monthly contribution into Regular Savings: at least ₦5,000, no upper
    limit. Only values still at their defaults are changed, so figures an
    officer has already set are kept.
    """
    SavingsProduct = apps.get_model("savings", "SavingsProduct")
    regular = SavingsProduct.objects.filter(code="REGULAR")
    regular.filter(min_contribution=0).update(min_contribution=Decimal("5000.00"))
    regular.filter(expected_monthly_contribution=0).update(expected_monthly_contribution=Decimal("5000.00"))
    regular.filter(max_monthly_contribution=Decimal("1000000.00")).update(max_monthly_contribution=None)


class Migration(migrations.Migration):

    dependencies = [
        ("savings", "0005_max_monthly_contribution"),
    ]

    operations = [
        migrations.RunPython(set_emdi_limits, migrations.RunPython.noop),
    ]
