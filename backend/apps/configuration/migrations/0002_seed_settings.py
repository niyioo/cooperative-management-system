from django.db import migrations


def create_settings(apps, schema_editor):
    CooperativeSettings = apps.get_model("configuration", "CooperativeSettings")
    CooperativeSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [
        ("configuration", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_settings, migrations.RunPython.noop),
    ]
