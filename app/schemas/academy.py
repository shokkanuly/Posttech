from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.models.enums import EnrollmentStatus


class LessonBrief(BaseModel):
    id: int
    order_index: int
    title: str
    is_completed: bool


class CourseResponse(BaseModel):
    id: int
    code: str
    title: str
    category: str
    description: str
    duration_minutes: int
    is_mandatory: bool
    due_date: Optional[date] = None
    total_lessons: int
    cover_gradient: str
    status: EnrollmentStatus
    progress_percent: float

    model_config = ConfigDict(from_attributes=True)


class CourseDetailResponse(CourseResponse):
    lessons: List[LessonBrief] = []
    current_lesson_id: Optional[int] = None


class LessonDetailResponse(BaseModel):
    id: int
    course_id: int
    order_index: int
    title: str
    content_markdown: str
    quiz_question: Optional[str] = None
    quiz_options: List[str] = []
    is_completed: bool


class QuizSubmitRequest(BaseModel):
    answer_index: int


class QuizSubmitResponse(BaseModel):
    passed: bool
    correct_index: int
    explanation: str
    new_progress_percent: float
    course_completed: bool
