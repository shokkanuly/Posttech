"""Explicit HR policy precedence and nullable course provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0010_source_metadata"
down_revision = "0009_domain_checks"
branch_labels = None
depends_on = None


def upgrade():
    for column in [
        sa.Column("policy_key", sa.String(100)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_until", sa.Date()),
        sa.Column("known_conflict", sa.Boolean(), nullable=False, server_default=sa.false()),
    ]:
        op.add_column("knowledge_documents", column)
    op.add_column("courses", sa.Column("is_synthetic", sa.Boolean()))


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
