from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Date as SQLDate
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EnrollmentStatus


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # e.g., "CRS-SEC-101"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), default="Compliance & Security", nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    due_date: Mapped[date | None] = mapped_column(SQLDate, nullable=True)
    total_lessons: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    cover_gradient: Mapped[str] = mapped_column(
        String(100), default="linear-gradient(145deg, #d9f27a, #84c99a)", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    lessons: Mapped[list[Lesson]] = relationship(
        "Lesson",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index.asc()",
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment", back_populates="course", cascade="all, delete-orphan"
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    quiz_question: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quiz_options_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of string options
    quiz_correct_answer: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Index of correct answer (0-based)

    # Relationships
    course: Mapped[Course] = relationship("Course", back_populates="lessons")
    progress_records: Mapped[list[LessonProgress]] = relationship(
        "LessonProgress", back_populates="lesson", cascade="all, delete-orphan"
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (Index("uq_enrollment_user_course", "user_id", "course_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        SQLEnum(EnrollmentStatus), default=EnrollmentStatus.NOT_STARTED, nullable=False
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="enrollments")
    course: Mapped[Course] = relationship("Course", back_populates="enrollments")
    lesson_progress: Mapped[list[LessonProgress]] = relationship(
        "LessonProgress", back_populates="enrollment", cascade="all, delete-orphan"
    )


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        Index("uq_progress_enrollment_lesson", "enrollment_id", "lesson_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    enrollment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiz_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    enrollment: Mapped[Enrollment] = relationship("Enrollment", back_populates="lesson_progress")
    lesson: Mapped[Lesson] = relationship("Lesson", back_populates="progress_records")


if TYPE_CHECKING:
    from app.models.user import User
