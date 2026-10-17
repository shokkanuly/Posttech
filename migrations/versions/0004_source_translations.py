"""Store reviewed source translations beside the original source text.

Revision ID: 0004_source_translations
Revises: 0003_knowledge_revisions
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_source_translations"
down_revision = "0003_knowledge_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "knowledge_documents",
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
    )
    for table in ("knowledge_documents", "knowledge_chunks"):
        op.add_column(
            table, sa.Column("translations", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade():
    raise RuntimeError("Forward-only migration; restore an operator-approved backup instead")
