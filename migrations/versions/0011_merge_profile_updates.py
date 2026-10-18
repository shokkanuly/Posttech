"""Join deployed profile and gateway histories without renaming either branch."""

import re

import sqlalchemy as sa
from alembic import op

revision = "0011_merge_profile_updates"
down_revision = ("0010_source_metadata", "0006_profile_updates")
branch_labels = None
depends_on = None

REQUEST_DOMAIN = """
status IN ('PENDING','APPROVED','REJECTED')
AND CAST(type AS VARCHAR) IN ('VACATION','ADVANCE_PAYMENT','PROFILE_UPDATE')
AND (end_date IS NULL OR end_date >= start_date)
AND (amount IS NULL OR amount > 0)
AND (charged_leave_days IS NULL OR charged_leave_days >= 0)
AND (
    (CAST(type AS VARCHAR)='VACATION' AND amount IS NULL AND {empty_profile})
    OR (CAST(type AS VARCHAR)='ADVANCE_PAYMENT' AND amount IS NOT NULL AND end_date IS NULL AND {empty_profile})
    OR (CAST(type AS VARCHAR)='PROFILE_UPDATE' AND amount IS NULL AND end_date IS NULL AND {profile_object} AND charged_leave_days IS NULL)
)
"""


def upgrade():
    connection = op.get_bind()
    json_type = "json_typeof" if connection.dialect.name == "postgresql" else "json_type"
    # Existing main rows may encode absent JSON as either SQL NULL or JSON null.
    # Accept both representations without rewriting any business data.
    condition = REQUEST_DOMAIN.format(
        empty_profile=f"(profile_changes IS NULL OR {json_type}(profile_changes)='null')",
        profile_object=f"(profile_changes IS NOT NULL AND {json_type}(profile_changes)='object')",
    )
    if connection.scalar(sa.text(f"SELECT count(*) FROM requests WHERE NOT ({condition})")):
        raise RuntimeError("Invalid request domains; operator review required before merge upgrade")
    if connection.dialect.name == "postgresql":
        op.drop_constraint("ck_requests_domain", "requests", type_="check")
        op.create_check_constraint("ck_requests_domain", "requests", condition)
    else:
        columns = [column["name"] for column in sa.inspect(connection).get_columns("requests")]
        guarded = condition
        for column in sorted(columns, key=len, reverse=True):
            guarded = re.sub(r"\b" + column + r"\b", "NEW." + column, guarded)
        for action in ("INSERT", "UPDATE"):
            op.execute(sa.text(f"DROP TRIGGER ck_requests_{action.lower()}"))
            op.execute(
                sa.text(
                    f"CREATE TRIGGER ck_requests_{action.lower()} BEFORE {action} ON requests "
                    f"WHEN NOT ({guarded}) BEGIN SELECT RAISE(ABORT, 'Invalid domain values'); END"
                )
            )


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
