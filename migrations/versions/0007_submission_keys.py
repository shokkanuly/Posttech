"""Employee-scoped submission idempotency; preserve every existing request."""

import sqlalchemy as sa
from alembic import op

revision = "0007_submission_keys"
down_revision = "0006_gateway_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("requests", sa.Column("submission_key", sa.String(80)))
    op.add_column("requests", sa.Column("submission_hash", sa.String(64)))
    op.create_index("uq_request_submission", "requests", ["user_id", "submission_key"], unique=True)


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
