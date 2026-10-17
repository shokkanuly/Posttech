"""Add the integration outbox, gateway nonces and request integration progress.

Revision ID: 0005_integration_outbox
Revises: 0004_source_translations
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_integration_outbox"
down_revision = "0004_source_translations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("requests", sa.Column("integration_status", sa.String(20), nullable=True))
    op.create_table(
        "integration_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_integration_outbox_request_id", "integration_outbox", ["request_id"])
    op.create_index(
        "ix_integration_outbox_due", "integration_outbox", ["status", "next_attempt_at"]
    )
    op.create_table(
        "integration_nonces",
        sa.Column("nonce", sa.String(64), primary_key=True),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_integration_nonces_seen_at", "integration_nonces", ["seen_at"])


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
