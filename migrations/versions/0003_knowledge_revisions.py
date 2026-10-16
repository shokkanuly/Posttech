"""Tie knowledge approval to the document revision reviewed by HR.

Revision ID: 0003_knowledge_revisions
Revises: 0002_sessions_and_approvals
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_knowledge_revisions"
down_revision = "0002_sessions_and_approvals"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "knowledge_documents",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
