"""Preflight legacy data, then enforce domains without rebuilding SQLite tables."""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = "0009_domain_checks"
down_revision = "0008_recovery"
branch_labels = None
depends_on = None

DOMAINS = {
    "requests": "status IN ('PENDING','APPROVED','REJECTED') AND CAST(type AS VARCHAR) IN ('VACATION','ADVANCE_PAYMENT','PROFILE_UPDATE') AND (end_date IS NULL OR end_date >= start_date) AND (amount IS NULL OR amount > 0) AND (charged_leave_days IS NULL OR charged_leave_days >= 0) AND ((type='VACATION' AND amount IS NULL) OR (CAST(type AS VARCHAR)='ADVANCE_PAYMENT' AND amount IS NOT NULL AND end_date IS NULL) OR (CAST(type AS VARCHAR)='PROFILE_UPDATE' AND amount IS NULL AND end_date IS NULL))",
    "employee_profiles": "leave_balance_days >= 0 AND (source_balance_days IS NULL OR source_balance_days >= 0)",
}


def upgrade():
    connection = op.get_bind()
    for table, condition in DOMAINS.items():
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table} WHERE NOT ({condition})")):
            raise RuntimeError(
                "Invalid legacy domain values; operator review required before upgrade"
            )
    for amount in connection.execute(
        sa.text("SELECT amount FROM requests WHERE amount IS NOT NULL")
    ).scalars():
        value = Decimal(str(amount))
        if (
            not value.is_finite()
            or value != value.quantize(Decimal("0.01"))
            or value > Decimal("9999999999.99")
        ):
            raise RuntimeError("Legacy monetary values require operator review before conversion")
    if connection.dialect.name == "postgresql":
        op.alter_column(
            "requests", "amount", type_=sa.Numeric(12, 2), postgresql_using="amount::numeric(12,2)"
        )
        for table, condition in DOMAINS.items():
            op.create_check_constraint("ck_" + table + "_domain", table, condition)
    else:
        # SQLite cannot add CHECKs without a table rebuild. Equivalent guards preserve
        # parent/child rows and FK enforcement; SQLite is not a fixed-decimal engine.
        for table, condition in DOMAINS.items():
            guarded = condition
            import re

            columns = [c["name"] for c in sa.inspect(connection).get_columns(table)]
            for column in sorted(columns, key=len, reverse=True):
                guarded = re.sub(r"\b" + column + r"\b", "NEW." + column, guarded)
            for action in ("INSERT", "UPDATE"):
                op.execute(
                    sa.text(
                        f"CREATE TRIGGER ck_{table}_{action.lower()} BEFORE {action} ON {table} WHEN NOT ({guarded}) BEGIN SELECT RAISE(ABORT, 'Invalid domain values'); END"
                    )
                )


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
