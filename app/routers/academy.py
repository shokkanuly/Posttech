from typing import List

from fastapi import APIRouter, Depends
from fastapi import Request as FastAPIRequest
from pydantic import PositiveInt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.academy import (
    CourseDetailResponse,
    CourseResponse,
    LessonDetailResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.academy_service import academy_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/courses", tags=["Jana Academy"])


@router.get("", response_model=List[CourseResponse])
def get_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return academy_service.get_user_courses(db, current_user)


@router.post("/{course_id}/enroll", response_model=CourseDetailResponse)
def enroll_course(
    course_id: PositiveInt,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return academy_service.enroll(db, current_user.id, course_id, current_user.id)


@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course_detail(
    course_id: PositiveInt,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return academy_service.get_course_detail(db, course_id, current_user)


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
def get_lesson(
    lesson_id: PositiveInt,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return academy_service.get_lesson_detail(db, lesson_id, current_user)


@router.post("/lessons/{lesson_id}/quiz", response_model=QuizSubmitResponse)
def submit_quiz(
    lesson_id: PositiveInt,
    payload: QuizSubmitRequest,
    request: FastAPIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ip_addr = request.client.host if request.client else None
    return academy_service.submit_lesson_quiz(
        db=db,
        lesson_id=lesson_id,
        user=current_user,
        answer_index=payload.answer_index,
        ip_address=ip_addr,
    )
