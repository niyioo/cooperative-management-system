"""
BR-40: members and Christmas savers may withdraw from their Christmas Savings any time while the
cycle is open. An officer records the withdrawal; a second officer approves it.
"""
from django.db import migrations


def apply(apps, schema_editor):
    apps.get_model("savings", "SavingsProduct").objects.filter(code="CHRISTMAS").update(allow_officer_withdrawal=True)


class Migration(migrations.Migration):
    dependencies = [("savings", "0010_pre_retirement_savings")]

    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
