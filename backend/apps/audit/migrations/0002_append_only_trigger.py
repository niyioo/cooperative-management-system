"""Reject UPDATE and DELETE on the audit log at the database level (BR-15)."""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION audit_log_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'The audit log is append-only; % is not allowed.', TG_OP
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE TRIGGER audit_log_guard
    BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION audit_log_guard();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS audit_log_guard ON audit_auditlog;
DROP FUNCTION IF EXISTS audit_log_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
