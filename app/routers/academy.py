from typing import List
from fastapi import APIRouter, Depends, Request as FastAPIRequest
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.academy import (
    CourseResponse,
    CourseDetailResponse,
    LessonDetailResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services.auth_service import get_current_user
from app.services.academy_service import academy_service

router = APIRouter(prefix="/courses", tags=["Jana Academy"])


@router.get("", response_model=List[CourseResponse])
def get_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return academy_service.get_user_courses(db, current_user)


@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course_detail(
    course_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return academy_service.get_course_detail(db, course_id, current_user)


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
def get_lesson(
    lesson_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return academy_service.get_lesson_detail(db, lesson_id, current_user)


@router.post("/lessons/{lesson_id}/quiz", response_model=QuizSubmitResponse)
def submit_quiz(
    lesson_id: int,
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
