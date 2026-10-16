"""Freeze the original schema; adopt a complete legacy database without deleting rows."""

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

EXPECTED = {
    "courses": [
        "id",
        "code",
        "title",
        "category",
        "description",
        "duration_minutes",
        "is_mandatory",
        "due_date",
        "total_lessons",
        "cover_gradient",
        "created_at",
    ],
    "knowledge_documents": [
        "id",
        "title",
        "category",
        "description",
        "version",
        "is_active",
        "created_at",
        "updated_at",
    ],
    "users": ["id", "email", "password_hash", "full_name", "role", "is_active", "created_at"],
    "audit_events": [
        "id",
        "actor_id",
        "action",
        "target_type",
        "target_id",
        "details_json",
        "ip_address",
        "created_at",
    ],
    "employee_profiles": [
        "id",
        "user_id",
        "employee_code",
        "company",
        "department",
        "position",
        "manager_id",
        "hire_date",
        "leave_balance_days",
        "location",
    ],
    "enrollments": [
        "id",
        "user_id",
        "course_id",
        "status",
        "progress_percent",
        "score",
        "completed_at",
        "updated_at",
    ],
    "knowledge_chunks": [
        "id",
        "document_id",
        "section_title",
        "content",
        "tags",
        "access_level",
        "created_at",
    ],
    "lessons": [
        "id",
        "course_id",
        "order_index",
        "title",
        "content_markdown",
        "quiz_question",
        "quiz_options_json",
        "quiz_correct_answer",
    ],
    "notifications": [
        "id",
        "user_id",
        "title",
        "message",
        "type",
        "is_read",
        "reference_type",
        "reference_id",
        "created_at",
    ],
    "requests": [
        "id",
        "request_code",
        "user_id",
        "type",
        "start_date",
        "end_date",
        "amount",
        "reason",
        "status",
        "reviewer_id",
        "review_comment",
        "external_sync_id",
        "created_at",
        "updated_at",
    ],
    "lesson_progress": [
        "id",
        "enrollment_id",
        "lesson_id",
        "is_completed",
        "quiz_passed",
        "completed_at",
    ],
    "request_events": ["id", "request_id", "actor_id", "event_type", "comment", "created_at"],
}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names()) & set(EXPECTED)
    if existing:
        if existing != set(EXPECTED):
            raise RuntimeError(
                "Partial legacy schema: restore or repair the database before migrating"
            )
        for table, columns in EXPECTED.items():
            if not set(columns).issubset({c["name"] for c in inspector.get_columns(table)}):
                raise RuntimeError(
                    "Legacy schema has missing columns; migration stopped without deleting data"
                )
        return
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("total_lessons", sa.Integer(), nullable=False),
        sa.Column("cover_gradient", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_courses_code", "courses", ["code"], unique=True)
    op.create_index("ix_courses_id", "courses", ["id"], unique=False)
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_id", "knowledge_documents", ["id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role", sa.Enum("EMPLOYEE", "MANAGER", "HR_ADMIN", name="userrole"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=50), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"], unique=False)
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"], unique=False)
    op.create_index("ix_audit_events_id", "audit_events", ["id"], unique=False)
    op.create_table(
        "employee_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employee_code", sa.String(length=50), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=255), nullable=False),
        sa.Column("manager_id", sa.Integer(), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("leave_balance_days", sa.Float(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_employee_profiles_employee_code", "employee_profiles", ["employee_code"], unique=True
    )
    op.create_index("ix_employee_profiles_id", "employee_profiles", ["id"], unique=False)
    op.create_index(
        "ix_employee_profiles_manager_id", "employee_profiles", ["manager_id"], unique=False
    )
    op.create_index("ix_employee_profiles_user_id", "employee_profiles", ["user_id"], unique=True)
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("NOT_STARTED", "IN_PROGRESS", "COMPLETED", name="enrollmentstatus"),
            nullable=False,
        ),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"], unique=False)
    op.create_index("ix_enrollments_id", "enrollments", ["id"], unique=False)
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"], unique=False)
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.String(length=255), nullable=True),
        sa.Column("access_level", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"], unique=False
    )
    op.create_index("ix_knowledge_chunks_id", "knowledge_chunks", ["id"], unique=False)
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("quiz_question", sa.String(length=500), nullable=True),
        sa.Column("quiz_options_json", sa.Text(), nullable=True),
        sa.Column("quiz_correct_answer", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lessons_course_id", "lessons", ["course_id"], unique=False)
    op.create_index("ix_lessons_id", "lessons", ["id"], unique=False)
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "type", sa.Enum("REQUEST", "ACADEMY", "SYSTEM", name="notificationtype"), nullable=False
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=False)
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_code", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "type", sa.Enum("VACATION", "ADVANCE_PAYMENT", name="requesttype"), nullable=False
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="requeststatus"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("external_sync_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requests_id", "requests", ["id"], unique=False)
    op.create_index("ix_requests_request_code", "requests", ["request_code"], unique=True)
    op.create_index("ix_requests_reviewer_id", "requests", ["reviewer_id"], unique=False)
    op.create_index("ix_requests_status", "requests", ["status"], unique=False)
    op.create_index("ix_requests_user_id", "requests", ["user_id"], unique=False)
    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False),
        sa.Column("quiz_passed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lesson_progress_enrollment_id", "lesson_progress", ["enrollment_id"], unique=False
    )
    op.create_index("ix_lesson_progress_id", "lesson_progress", ["id"], unique=False)
    op.create_index("ix_lesson_progress_lesson_id", "lesson_progress", ["lesson_id"], unique=False)
    op.create_table(
        "request_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum("SUBMITTED", "APPROVED", "REJECTED", "COMMENTED", name="requesteventtype"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_events_id", "request_events", ["id"], unique=False)
    op.create_index("ix_request_events_request_id", "request_events", ["request_id"], unique=False)


def downgrade():
    raise RuntimeError("Forward-only migrations: restore an operator-approved backup instead")
