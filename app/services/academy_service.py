import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import EnrollmentStatus, NotificationType
from app.models.user import User
from app.models.academy import Course, Lesson, Enrollment, LessonProgress
from app.schemas.academy import (
    CourseResponse,
    CourseDetailResponse,
    LessonBrief,
    LessonDetailResponse,
    QuizSubmitResponse,
)
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service


class AcademyService:
    @staticmethod
    def get_or_create_enrollment(db: Session, user_id: int, course_id: int) -> Enrollment:
        enrollment = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
            .first()
        )
        if not enrollment:
            enrollment = Enrollment(
                user_id=user_id,
                course_id=course_id,
                status=EnrollmentStatus.NOT_STARTED,
                progress_percent=0.0,
            )
            db.add(enrollment)
            db.flush()
        return enrollment

    @classmethod
    def get_user_courses(cls, db: Session, user: User) -> List[CourseResponse]:
        courses = db.query(Course).order_by(Course.id.asc()).all()
        results = []
        for course in courses:
            enrollment = cls.get_or_create_enrollment(db, user.id, course.id)
            results.append(
                CourseResponse(
                    id=course.id,
                    code=course.code,
                    title=course.title,
                    category=course.category,
                    description=course.description,
                    duration_minutes=course.duration_minutes,
                    is_mandatory=course.is_mandatory,
                    due_date=course.due_date,
                    total_lessons=course.total_lessons,
                    cover_gradient=course.cover_gradient,
                    status=enrollment.status,
                    progress_percent=enrollment.progress_percent,
                )
            )
        return results

    @classmethod
    def get_course_detail(cls, db: Session, course_id: int, user: User) -> CourseDetailResponse:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

        enrollment = cls.get_or_create_enrollment(db, user.id, course.id)

        # Get all completed lesson IDs for this enrollment
        completed_lesson_ids = {
            lp.lesson_id
            for lp in db.query(LessonProgress)
            .filter(LessonProgress.enrollment_id == enrollment.id, LessonProgress.is_completed == True)
            .all()
        }

        lessons_brief = []
        first_incomplete_id = None
        for lesson in course.lessons:
            is_comp = lesson.id in completed_lesson_ids
            lessons_brief.append(
                LessonBrief(
                    id=lesson.id,
                    order_index=lesson.order_index,
                    title=lesson.title,
                    is_completed=is_comp,
                )
            )
            if not is_comp and first_incomplete_id is None:
                first_incomplete_id = lesson.id

        current_id = first_incomplete_id or (course.lessons[0].id if course.lessons else None)

        return CourseDetailResponse(
            id=course.id,
            code=course.code,
            title=course.title,
            category=course.category,
            description=course.description,
            duration_minutes=course.duration_minutes,
            is_mandatory=course.is_mandatory,
            due_date=course.due_date,
            total_lessons=course.total_lessons,
            cover_gradient=course.cover_gradient,
            status=enrollment.status,
            progress_percent=enrollment.progress_percent,
            lessons=lessons_brief,
            current_lesson_id=current_id,
        )

    @classmethod
    def get_lesson_detail(cls, db: Session, lesson_id: int, user: User) -> LessonDetailResponse:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        enrollment = cls.get_or_create_enrollment(db, user.id, lesson.course_id)
        lp = (
            db.query(LessonProgress)
            .filter(LessonProgress.enrollment_id == enrollment.id, LessonProgress.lesson_id == lesson.id)
            .first()
        )
        is_comp = lp.is_completed if lp else False

        options = json.loads(lesson.quiz_options_json) if lesson.quiz_options_json else []

        return LessonDetailResponse(
            id=lesson.id,
            course_id=lesson.course_id,
            order_index=lesson.order_index,
            title=lesson.title,
            content_markdown=lesson.content_markdown,
            quiz_question=lesson.quiz_question,
            quiz_options=options,
            is_completed=is_comp,
        )

    @classmethod
    def submit_lesson_quiz(
        cls,
        db: Session,
        lesson_id: int,
        user: User,
        answer_index: int,
        ip_address: Optional[str] = None,
    ) -> QuizSubmitResponse:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

        enrollment = cls.get_or_create_enrollment(db, user.id, lesson.course_id)
        course = lesson.course

        # Check if quiz is correct
        passed = (lesson.quiz_correct_answer is None) or (answer_index == lesson.quiz_correct_answer)

        # Retrieve or create LessonProgress
        lp = (
            db.query(LessonProgress)
            .filter(LessonProgress.enrollment_id == enrollment.id, LessonProgress.lesson_id == lesson.id)
            .first()
        )
        if not lp:
            lp = LessonProgress(
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                is_completed=passed,
                quiz_passed=passed,
                completed_at=datetime.now(timezone.utc) if passed else None,
            )
            db.add(lp)
        else:
            if passed:
                lp.is_completed = True
                lp.quiz_passed = True
                lp.completed_at = datetime.now(timezone.utc)

        db.flush()

        # Recalculate enrollment progress
        total_lessons = db.query(Lesson).filter(Lesson.course_id == course.id).count()
        completed_lessons = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.enrollment_id == enrollment.id,
                LessonProgress.is_completed == True,
            )
            .count()
        )

        progress_pct = round((completed_lessons / max(1, total_lessons)) * 100, 1)
        enrollment.progress_percent = min(100.0, progress_pct)
        enrollment.status = (
            EnrollmentStatus.COMPLETED if progress_pct >= 100.0 else EnrollmentStatus.IN_PROGRESS
        )
        if progress_pct >= 100.0 and not enrollment.completed_at:
            enrollment.completed_at = datetime.now(timezone.utc)
            # Create completion notification
            notification_service.create_notification(
                db=db,
                user_id=user.id,
                title="Course completed! 🎓",
                message=f"Congratulations! You completed '{course.title}' with 100% progress.",
                type=NotificationType.ACADEMY,
                reference_type="course",
                reference_id=course.code,
            )

        db.commit()
        db.refresh(enrollment)

        explanation = (
            "Correct! You identified the appropriate data protection practice."
            if passed
            else "That is not quite right. Review the policy points and try again."
        )

        return QuizSubmitResponse(
            passed=passed,
            correct_index=lesson.quiz_correct_answer or 0,
            explanation=explanation,
            new_progress_percent=enrollment.progress_percent,
            course_completed=(enrollment.status == EnrollmentStatus.COMPLETED),
        )

    @classmethod
    def get_user_overall_learning_progress(cls, db: Session, user_id: int) -> float:
        """Returns the average progress across all assigned courses for dashboard display."""
        enrollments = db.query(Enrollment).filter(Enrollment.user_id == user_id).all()
        if not enrollments:
            return 0.0
        total = sum(e.progress_percent for e in enrollments)
        return round(total / len(enrollments), 1)


academy_service = AcademyService()
