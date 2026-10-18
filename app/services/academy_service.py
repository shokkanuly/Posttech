import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session, selectinload

from app.models.academy import Course, Enrollment, Lesson, LessonProgress
from app.models.enums import EnrollmentStatus, NotificationType
from app.models.user import User
from app.schemas.academy import (
    CourseDetailResponse,
    CourseResponse,
    LessonBrief,
    LessonDetailResponse,
    QuizSubmitResponse,
)
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service


class AcademyService:
    @staticmethod
    def get_enrollment(db: Session, user_id: int, course_id: int):
        return (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user_id, Enrollment.course_id == course_id)
            .first()
        )

    @classmethod
    def enroll(cls, db: Session, user_id: int, course_id: int, actor_id: int):
        course = db.get(Course, course_id)
        user = db.get(User, user_id)
        if not course or not user or not user.is_active:
            raise HTTPException(404, "Active user or course not found")
        db.execute(
            update(User).where(User.id == user_id).values(is_active=User.is_active),
            execution_options={"synchronize_session": False},
        )
        enrollment = cls.get_enrollment(db, user_id, course_id)
        if not enrollment:
            enrollment = Enrollment(
                user_id=user_id,
                course_id=course_id,
                status=EnrollmentStatus.NOT_STARTED,
                progress_percent=0,
            )
            db.add(enrollment)
            db.flush()
            notification_service.create_notification(
                db,
                user_id,
                "Course assigned",
                course.title,
                NotificationType.ACADEMY,
                "course",
                course.code,
            )
            audit_service.log_event(
                db,
                action="COURSE_ASSIGNED",
                actor_id=actor_id,
                target_type="enrollment",
                target_id=str(enrollment.id),
                details={"user_id": user_id, "course_id": course_id},
            )
        db.commit()
        return cls.get_course_detail(db, course_id, user)

    @classmethod
    def course_response(cls, course: Course, enrollment: Enrollment | None):
        return CourseResponse(
            id=course.id,
            code=course.code,
            title=course.title,
            category=course.category,
            description=course.description,
            duration_minutes=course.duration_minutes,
            is_mandatory=course.is_mandatory,
            due_date=course.due_date,
            total_lessons=len(course.lessons),
            cover_gradient=course.cover_gradient,
            assigned=enrollment is not None,
            status=enrollment.status if enrollment else EnrollmentStatus.NOT_STARTED,
            progress_percent=enrollment.progress_percent if enrollment else 0,
            score=enrollment.score if enrollment else None,
            completed_at=enrollment.completed_at if enrollment else None,
        )

    @classmethod
    def get_user_courses(cls, db: Session, user: User, limit: int | None = None, offset: int = 0):
        enrollments = {
            e.course_id: e for e in db.query(Enrollment).filter(Enrollment.user_id == user.id).all()
        }
        return [
            cls.course_response(c, enrollments.get(c.id))
            for c in db.query(Course)
            .options(selectinload(Course.lessons))
            .order_by(Course.id)
            .offset(offset)
            .limit(limit)
            .all()
        ]

    @classmethod
    def get_course_detail(cls, db: Session, course_id: int, user: User):
        course = db.get(Course, course_id)
        if not course:
            raise HTTPException(404, "Course not found")
        enrollment = cls.get_enrollment(db, user.id, course_id)
        completed = (
            {p.lesson_id for p in enrollment.lesson_progress if p.is_completed}
            if enrollment
            else set()
        )
        lessons = [
            LessonBrief(
                id=lesson.id,
                order_index=lesson.order_index,
                title=lesson.title,
                is_completed=lesson.id in completed,
            )
            for lesson in course.lessons
        ]
        current = next(
            (lesson.id for lesson in lessons if not lesson.is_completed),
            lessons[0].id if lessons else None,
        )
        return CourseDetailResponse(
            **cls.course_response(course, enrollment).model_dump(),
            lessons=lessons,
            current_lesson_id=current,
        )

    @classmethod
    def get_lesson_detail(cls, db: Session, lesson_id: int, user: User):
        lesson = db.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(404, "Lesson not found")
        enrollment = cls.get_enrollment(db, user.id, lesson.course_id)
        completed = (
            any(p.lesson_id == lesson.id and p.is_completed for p in enrollment.lesson_progress)
            if enrollment
            else False
        )
        return LessonDetailResponse(
            id=lesson.id,
            course_id=lesson.course_id,
            order_index=lesson.order_index,
            title=lesson.title,
            content_markdown=lesson.content_markdown,
            quiz_question=lesson.quiz_question,
            quiz_options=json.loads(lesson.quiz_options_json or "[]"),
            is_completed=completed,
        )

    @classmethod
    def submit_lesson_quiz(
        cls, db: Session, lesson_id: int, user: User, answer_index: int, ip_address=None
    ):
        lesson = db.get(Lesson, lesson_id)
        if not lesson:
            raise HTTPException(404, "Lesson not found")
        options = json.loads(lesson.quiz_options_json or "[]")
        if options and not 0 <= answer_index < len(options):
            raise HTTPException(422, "Answer index is outside the available options")
        if not options and answer_index != 0:
            raise HTTPException(422, "Use answer_index 0 to acknowledge material without a quiz")
        enrollment = cls.get_enrollment(db, user.id, lesson.course_id)
        if not enrollment:
            raise HTTPException(409, "Enroll in the course before submitting progress")
        # Lessons are taken in order: a quiz opens once every earlier lesson is passed.
        done = {p.lesson_id for p in enrollment.lesson_progress if p.is_completed}
        if any(
            earlier.order_index < lesson.order_index and earlier.id not in done
            for earlier in lesson.course.lessons
        ):
            raise HTTPException(409, "Complete the previous lessons first")
        # Acquire an enrollment write lock before reading progress, also on SQLite.
        db.execute(
            update(Enrollment)
            .where(Enrollment.id == enrollment.id)
            .values(updated_at=datetime.now(timezone.utc)),
            execution_options={"synchronize_session": False},
        )
        db.refresh(enrollment)
        passed = lesson.quiz_correct_answer is None or answer_index == lesson.quiz_correct_answer
        progress = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.enrollment_id == enrollment.id, LessonProgress.lesson_id == lesson.id
            )
            .first()
        )
        if not progress:
            progress = LessonProgress(
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                is_completed=False,
                quiz_passed=False,
            )
            db.add(progress)
        if passed:
            progress.is_completed = True
            progress.quiz_passed = True
            progress.completed_at = progress.completed_at or datetime.now(timezone.utc)
        db.flush()
        total = db.query(Lesson).filter(Lesson.course_id == lesson.course_id).count()
        count = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.enrollment_id == enrollment.id, LessonProgress.is_completed.is_(True)
            )
            .count()
        )
        percent = round(count / max(1, total) * 100, 1)
        enrollment.progress_percent = percent
        enrollment.score = percent
        enrollment.status = (
            EnrollmentStatus.COMPLETED if count == total and total else EnrollmentStatus.IN_PROGRESS
        )
        if enrollment.status == EnrollmentStatus.COMPLETED and enrollment.completed_at is None:
            enrollment.completed_at = datetime.now(timezone.utc)
            notification_service.create_notification(
                db,
                user.id,
                "Course completed! 🎓",
                f"You completed {lesson.course.title}. Result: {percent:.0f}% of lessons passed.",
                NotificationType.ACADEMY,
                "course",
                lesson.course.code,
            )
        audit_service.log_event(
            db,
            action="LESSON_QUIZ_SUBMITTED",
            actor_id=user.id,
            target_type="lesson",
            target_id=str(lesson.id),
            details={"passed": passed, "progress_percent": percent},
        )
        db.commit()
        return QuizSubmitResponse(
            passed=passed,
            correct_index=(lesson.quiz_correct_answer or 0) if passed else None,
            explanation="Correct. Lesson completed."
            if passed
            else "Review the material and try again.",
            new_progress_percent=percent,
            course_completed=enrollment.status == EnrollmentStatus.COMPLETED,
            score=percent,
        )

    @staticmethod
    def get_user_overall_learning_progress(db: Session, user_id: int) -> float:
        average = (
            db.query(func.avg(Enrollment.progress_percent))
            .filter(Enrollment.user_id == user_id)
            .scalar()
        )
        return round(float(average or 0.0), 1)


academy_service = AcademyService()
