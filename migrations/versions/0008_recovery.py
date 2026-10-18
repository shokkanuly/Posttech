"""Persist authorized recovery commands and callback generations."""

import sqlalchemy as sa
from alembic import op

revision = "0008_recovery"
down_revision = "0007_submission_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "integration_outbox",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("integration_outbox", sa.Column("retry_key", sa.String(32)))
    op.add_column("integration_outbox", sa.Column("recovery_key", sa.String(32)))


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
