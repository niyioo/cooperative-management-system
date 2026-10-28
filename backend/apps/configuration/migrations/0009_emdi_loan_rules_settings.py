"""
EMDI's loan rules (BR-37): the savings multiple applies to the cooperative (regular) loan only, set on the
product, so the society-wide borrowing limit (BR-32) is switched off; a member may guarantee as many loans as
they like (BR-31 off); and a member may hold at most three loans at once.
"""
from django.db import migrations


def apply(apps, schema_editor):
    apps.get_model("configuration", "CooperativeSettings").objects.update(
        loan_savings_multiple=None, guarantor_savings_multiple=None, max_running_loans=3
    )


class Migration(migrations.Migration):
    dependencies = [("configuration", "0008_emdi_loan_rules")]

    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
