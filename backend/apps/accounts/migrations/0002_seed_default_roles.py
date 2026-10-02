"""
Seed the default officer roles (ARCHITECTURE.md §3). Roles are created only if
missing, so edits officers make later are never overwritten. The matrix is
frozen here on purpose: migrations must not change behaviour when app code changes.
"""
from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

VIEW_ALL = [
    "members.view_member",
    "savings.view_savings",
    "loans.view_loans",
    "investments.view_investments",
    "dividends.view_dividends",
    "ledger.view_all_transactions",
    "closures.view_closure_requests",
]
REPORTS = ["reports.view_reports", "reports.export_reports"]

ROLES = {
    "Super Administrator": {
        "description": "Full access to every module, including officers, roles and settings.",
        "permissions": "__all__",
    },
    "Cooperative Chairman": {
        "description": "Oversight and final approvals: loans, dividends, closures, adjustments and batches.",
        "permissions": VIEW_ALL
        + REPORTS
        + [
            "loans.review_loan_application",
            "loans.approve_loan_application",
            "dividends.approve_dividends",
            "ledger.approve_transaction",
            "ledger.approve_batch",
            "closures.approve_closure_request",
            "notifications.manage_announcements",
            "notifications.send_notifications",
            "audit.view_audit_log",
        ],
    },
    "Cooperative Secretary": {
        "description": "Member registration and records, closure reviews and announcements.",
        "permissions": REPORTS
        + [
            "members.view_member",
            "members.add_member",
            "members.change_member",
            "members.import_members",
            "members.change_member_status",
            "members.manage_member_documents",
            "closures.view_closure_requests",
            "closures.review_closure_request",
            "notifications.manage_announcements",
            "notifications.send_notifications",
        ],
    },
    "Treasurer": {
        "description": "Cash control: contributions, disbursements, payouts, approvals and closures.",
        "permissions": VIEW_ALL
        + REPORTS
        + [
            "savings.manage_savings_products",
            "savings.manage_savings_cycles",
            "savings.close_savings_cycle",
            "savings.post_savings_contribution",
            "savings.post_savings_withdrawal",
            "loans.manage_loan_products",
            "loans.approve_loan_application",
            "loans.disburse_loan",
            "loans.record_loan_repayment",
            "loans.mark_loan_default",
            "dividends.manage_dividend_cycles",
            "dividends.calculate_dividends",
            "dividends.pay_dividends",
            "ledger.approve_transaction",
            "ledger.reverse_transaction",
            "ledger.post_adjustment",
            "ledger.manage_batches",
            "ledger.approve_batch",
            "closures.execute_account_closure",
        ],
    },
    "Accountant": {
        "description": "Book-keeping: contributions, repayments, investments, batches and dividend calculation.",
        "permissions": [
            "members.view_member",
            "savings.view_savings",
            "loans.view_loans",
            "investments.view_investments",
            "dividends.view_dividends",
            "ledger.view_all_transactions",
            "savings.manage_savings_products",
            "savings.manage_savings_cycles",
            "savings.close_savings_cycle",
            "savings.post_savings_contribution",
            "loans.record_loan_repayment",
            "investments.manage_investment_accounts",
            "investments.post_investment_transaction",
            "dividends.manage_dividend_cycles",
            "dividends.calculate_dividends",
            "ledger.reverse_transaction",
            "ledger.post_adjustment",
            "ledger.manage_batches",
        ]
        + REPORTS,
    },
    "Loan Officer": {
        "description": "Loan products, application reviews and repayment recording.",
        "permissions": [
            "members.view_member",
            "savings.view_savings",
            "loans.view_loans",
            "loans.manage_loan_products",
            "loans.review_loan_application",
            "loans.record_loan_repayment",
        ]
        + REPORTS,
    },
    "Investment Officer": {
        "description": "Investment schemes, member investments and dividend calculation.",
        "permissions": [
            "members.view_member",
            "investments.view_investments",
            "investments.manage_investment_products",
            "investments.manage_investment_accounts",
            "investments.post_investment_transaction",
            "dividends.view_dividends",
            "dividends.manage_dividend_cycles",
            "dividends.calculate_dividends",
        ]
        + REPORTS,
    },
    "Auditor": {
        "description": "Read-only access to all records, reports and the audit log (supervisory committee, external audit).",
        "permissions": VIEW_ALL + REPORTS + ["audit.view_audit_log"],
    },
}

CATALOGUE_APPS = [
    "accounts",
    "configuration",
    "audit",
    "members",
    "savings",
    "loans",
    "investments",
    "dividends",
    "ledger",
    "closures",
    "notifications",
    "reports",
]


def seed_roles(apps, schema_editor):
    # Permissions are normally created after all migrations run (post_migrate);
    # create them now so this migration can attach them to roles.
    for label in CATALOGUE_APPS:
        create_permissions(global_apps.get_app_config(label), apps=apps, verbosity=0)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    RoleProfile = apps.get_model("accounts", "RoleProfile")

    catalogue = {
        f"{p.content_type.app_label}.{p.codename}": p
        for p in Permission.objects.filter(content_type__app_label__in=CATALOGUE_APPS).select_related("content_type")
    }

    for name, spec in ROLES.items():
        group, created = Group.objects.get_or_create(name=name)
        RoleProfile.objects.update_or_create(
            group=group, defaults={"description": spec["description"], "is_system": True}
        )
        if not created:
            continue
        codes = catalogue.keys() if spec["permissions"] == "__all__" else spec["permissions"]
        missing = [c for c in codes if c not in catalogue]
        if missing:
            raise RuntimeError(f"Role '{name}' references unknown permissions: {missing}")
        group.permissions.set([catalogue[c] for c in codes])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("audit", "0002_append_only_trigger"),
        ("closures", "0002_initial"),
        ("configuration", "0002_seed_settings"),
        ("dividends", "0002_initial"),
        ("investments", "0002_initial"),
        ("ledger", "0003_append_only_trigger"),
        ("loans", "0001_initial"),
        ("members", "0001_initial"),
        ("notifications", "0001_initial"),
        ("reports", "0001_initial"),
        ("savings", "0002_seed_emdi_products"),
    ]

    operations = [
        migrations.RunPython(seed_roles, migrations.RunPython.noop),
    ]
