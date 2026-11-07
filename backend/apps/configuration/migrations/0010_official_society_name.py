"""The society's details from its forms: Reg. No. 9369, short name EMDI CMS Ltd, and its address."""
from django.db import migrations

OFFICIAL = {
    "name": "EMDI Cooperative Multipurpose Society Ltd",
    "short_name": "EMDI CMS Ltd",
    "registration_number": "9369",
    "address": "EMDI, KM 4, Ondo Road, Akure, Ondo State",
}
EARLIER_NAMES = ["EMDI Cooperative Multipurpose Society Ltd", "EMDI Cooperative Society",
                 "EMDI Department Staff Cooperative Multipurpose Society Limited"]


def apply(apps, schema_editor):
    Settings = apps.get_model("configuration", "CooperativeSettings")
    for settings in Settings.objects.all():
        if settings.name in EARLIER_NAMES or not settings.name:
            settings.name = OFFICIAL["name"]
            settings.short_name = OFFICIAL["short_name"]
        if not settings.registration_number:
            settings.registration_number = OFFICIAL["registration_number"]
        if settings.address in ("", "EMDI Complex, Akure"):
            settings.address = OFFICIAL["address"]
        settings.save()


class Migration(migrations.Migration):
    dependencies = [("configuration", "0009_emdi_loan_rules_settings")]

    operations = [migrations.RunPython(apply, migrations.RunPython.noop)]
