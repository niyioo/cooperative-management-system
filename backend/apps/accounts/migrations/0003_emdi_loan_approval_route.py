"""
EMDI's approval routes. Loans (BR-37): the Secretary collates applications, the Chairman approves;
the Secretary gains loan viewing and reviewing (with savings, to judge the request) and the Treasurer
no longer approves loans but still pays them out. Membership (BR-39): the Secretary recommends an
application, the Chairman approves it, so the Chairman may now change a member's status.
"""
from django.db import migrations

SECRETARY_GAINS = ["loans.view_loans", "loans.review_loan_application", "savings.view_savings"]
TREASURER_LOSES = ["loans.approve_loan_application"]
CHAIRMAN_GAINS = ["members.change_member_status"]


def _perms(Permission, codes):
    found = []
    for code in codes:
        app_label, codename = code.split(".")
        found.extend(Permission.objects.filter(content_type__app_label=app_label, codename=codename))
    return found


def apply(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    secretary = Group.objects.filter(name="Cooperative Secretary").first()
    if secretary:
        secretary.permissions.add(*_perms(Permission, SECRETARY_GAINS))
    treasurer = Group.objects.filter(name="Treasurer").first()
    if treasurer:
        treasurer.permissions.remove(*_perms(Permission, TREASURER_LOSES))
    chairman = Group.objects.filter(name="Cooperative Chairman").first()
    if chairman:
        chairman.permissions.add(*_perms(Permission, CHAIRMAN_GAINS))


def undo(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    secretary = Group.objects.filter(name="Cooperative Secretary").first()
    if secretary:
        secretary.permissions.remove(*_perms(Permission, SECRETARY_GAINS))
    treasurer = Group.objects.filter(name="Treasurer").first()
    if treasurer:
        treasurer.permissions.add(*_perms(Permission, TREASURER_LOSES))
    chairman = Group.objects.filter(name="Cooperative Chairman").first()
    if chairman:
        chairman.permissions.remove(*_perms(Permission, CHAIRMAN_GAINS))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_seed_default_roles"),
        ("loans", "0006_emdi_loan_rules"),
        ("members", "0004_emdi_forms_and_loan_rules"),
    ]

    operations = [migrations.RunPython(apply, undo)]
