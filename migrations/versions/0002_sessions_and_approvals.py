"""Add revocable sessions, explicit source approval, and learning uniqueness."""

import sqlalchemy as sa
from alembic import op

revision = "0002_sessions_and_approvals"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    # Stop on pre-existing duplicates; never delete or merge user records implicitly.
    connection = op.get_bind()
    for table, first, second in (
        ("enrollments", "user_id", "course_id"),
        ("lesson_progress", "enrollment_id", "lesson_id"),
    ):
        duplicate = connection.execute(
            sa.text(f"SELECT 1 FROM {table} GROUP BY {first}, {second} HAVING COUNT(*) > 1 LIMIT 1")
        ).first()
        if duplicate:
            raise RuntimeError(
                f"Duplicate {table} records require operator review before migration"
            )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.add_column(
        "knowledge_documents",
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Nullable approval metadata avoids rewriting existing SQLite tables.
    op.execute(
        "ALTER TABLE knowledge_documents ADD COLUMN approved_by_id INTEGER REFERENCES users(id)"
    )
    op.add_column("knowledge_documents", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.create_index(
        "uq_enrollment_user_course", "enrollments", ["user_id", "course_id"], unique=True
    )
    op.create_index(
        "uq_progress_enrollment_lesson",
        "lesson_progress",
        ["enrollment_id", "lesson_id"],
        unique=True,
    )


def downgrade():
    raise RuntimeError("Forward-only migrations: restore an operator-approved backup instead")
