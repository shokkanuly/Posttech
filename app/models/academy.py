from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, Date as SQLDate, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import EnrollmentStatus


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "CRS-SEC-101"
    title = Column(String(255), nullable=False)
    category = Column(String(100), default="Compliance & Security", nullable=False)
    description = Column(Text, nullable=False)
    duration_minutes = Column(Integer, default=20, nullable=False)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    due_date = Column(SQLDate, nullable=True)
    total_lessons = Column(Integer, default=4, nullable=False)
    cover_gradient = Column(String(100), default="linear-gradient(145deg, #d9f27a, #84c99a)", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan", order_by="Lesson.order_index.asc()")
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=1)
    title = Column(String(255), nullable=False)
    content_markdown = Column(Text, nullable=False)
    quiz_question = Column(String(500), nullable=True)
    quiz_options_json = Column(Text, nullable=True)  # JSON array of string options
    quiz_correct_answer = Column(Integer, nullable=True)  # Index of correct answer (0-based)

    # Relationships
    course = relationship("Course", back_populates="lessons")
    progress_records = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(SQLEnum(EnrollmentStatus), default=EnrollmentStatus.NOT_STARTED, nullable=False)
    progress_percent = Column(Float, default=0.0, nullable=False)
    score = Column(Float, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")
    lesson_progress = relationship("LessonProgress", back_populates="enrollment", cascade="all, delete-orphan")


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_id = Column(Integer, ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    quiz_passed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    enrollment = relationship("Enrollment", back_populates="lesson_progress")
    lesson = relationship("Lesson", back_populates="progress_records")
