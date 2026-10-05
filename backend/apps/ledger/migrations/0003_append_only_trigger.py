"""
Database-level immutability for the ledger (ARCHITECTURE.md D1, BR-17).

- New rows must be PENDING or POSTED.
- PENDING rows may only change their approval fields, and only to POSTED or REJECTED.
- POSTED rows may only change status to REVERSED.
- REJECTED and REVERSED rows are final.
- Rows can never be deleted.

This holds even for manual SQL sessions and ORM bugs. Violations raise
SQLSTATE 23000, which Django surfaces as IntegrityError.
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION ledger_transaction_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    approval_cols text[] := ARRAY['status', 'approved_by_id', 'approved_at', 'posted_at', 'updated_at'];
    status_cols   text[] := ARRAY['status', 'updated_at'];
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status NOT IN ('PENDING', 'POSTED') THEN
            RAISE EXCEPTION 'New ledger transactions must be PENDING or POSTED (got %).', NEW.status
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Ledger transaction % cannot be deleted; post a reversal instead.', OLD.reference
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    IF OLD.status = 'PENDING' THEN
        IF NEW.status NOT IN ('PENDING', 'POSTED', 'REJECTED') THEN
            RAISE EXCEPTION 'Pending transaction % can only be posted or rejected.', OLD.reference
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF (to_jsonb(NEW) - approval_cols) IS DISTINCT FROM (to_jsonb(OLD) - approval_cols) THEN
            RAISE EXCEPTION 'Pending transaction % may only change its approval fields.', OLD.reference
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSIF OLD.status = 'POSTED' THEN
        IF NEW.status NOT IN ('POSTED', 'REVERSED')
           OR (to_jsonb(NEW) - status_cols) IS DISTINCT FROM (to_jsonb(OLD) - status_cols) THEN
            RAISE EXCEPTION 'Posted transaction % is immutable; post a reversal instead.', OLD.reference
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    ELSE
        IF (to_jsonb(NEW) - 'updated_at') IS DISTINCT FROM (to_jsonb(OLD) - 'updated_at') THEN
            RAISE EXCEPTION 'Transaction % is % and cannot be changed.', OLD.reference, OLD.status
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER ledger_transaction_guard
    BEFORE INSERT OR UPDATE OR DELETE ON ledger_transaction
    FOR EACH ROW EXECUTE FUNCTION ledger_transaction_guard();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS ledger_transaction_guard ON ledger_transaction;
DROP FUNCTION IF EXISTS ledger_transaction_guard();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
