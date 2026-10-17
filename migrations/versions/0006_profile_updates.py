"""Add profile contact fields and approval-based profile update requests.

Revision ID: 0006_profile_updates
Revises: 0005_integration_outbox
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_profile_updates"
down_revision = "0005_integration_outbox"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        # Native enum on PostgreSQL; SQLite stores the name as plain text.
        op.execute("ALTER TYPE requesttype ADD VALUE IF NOT EXISTS 'PROFILE_UPDATE'")
    op.add_column("employee_profiles", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column(
        "employee_profiles", sa.Column("emergency_contact", sa.String(255), nullable=True)
    )
    op.add_column("requests", sa.Column("profile_changes", sa.JSON(), nullable=True))


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
