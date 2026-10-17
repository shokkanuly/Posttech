"""Durable canonical document delivery and read-only profile snapshots.

Existing rows are retained. Old contract jobs require explicit operator review.
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_gateway_runtime"
down_revision = "0005_integration_outbox"
branch_labels = None
depends_on = None


def upgrade():
    for col in [
        sa.Column("payload", sa.JSON()),
        sa.Column("gateway_job_id", sa.String(36)),
        sa.Column("sent_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
    ]:
        op.add_column("integration_outbox", col)
    for col in [
        sa.Column("integration_mode", sa.String(20)),
        sa.Column("gateway_job_id", sa.String(36)),
        sa.Column("integration_completed_at", sa.DateTime()),
        sa.Column("charged_leave_days", sa.Float()),
        sa.Column(
            "leave_balance_confirmed", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    ]:
        op.add_column("requests", col)
    for col in [
        sa.Column("source_mode", sa.String(20), nullable=False, server_default="LOCAL"),
        sa.Column("source_balance_days", sa.Float()),
        sa.Column("source_as_of", sa.DateTime()),
        sa.Column("synced_at", sa.DateTime()),
    ]:
        op.add_column("employee_profiles", col)
    op.create_table(
        "integration_sync_state",
        sa.Column("name", sa.String(30), primary_key=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("cursor", sa.DateTime()),
        sa.Column("last_attempt_at", sa.DateTime()),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column("last_error", sa.String(40)),
        sa.Column("records_count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "integration_reviews",
        sa.Column("employee_code", sa.String(50), primary_key=True),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )
    # Preserve old rows for HR review; never reinterpret or replay the old vendor-shaped contract.
    op.execute(
        sa.text(
            "UPDATE integration_outbox SET status='DEAD', last_error='LEGACY_CONTRACT' WHERE status='PENDING'"
        )
    )


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
