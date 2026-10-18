from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EnrollmentStatus
from app.schemas.common import BodyDatabaseID, UTCDateTime


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
    due_date: date | None = None
    total_lessons: int
    cover_gradient: str
    assigned: bool
    status: EnrollmentStatus
    progress_percent: float
    score: float | None = None
    completed_at: UTCDateTime | None = None

    model_config = ConfigDict(from_attributes=True)


class CourseDetailResponse(CourseResponse):
    lessons: list[LessonBrief] = Field(default_factory=list)
    current_lesson_id: int | None = None


class LessonDetailResponse(BaseModel):
    id: int
    course_id: int
    order_index: int
    title: str
    content_markdown: str
    quiz_question: str | None = None
    quiz_options: list[str] = Field(default_factory=list)
    is_completed: bool


class QuizSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_index: int = Field(ge=0, strict=True)


class QuizSubmitResponse(BaseModel):
    passed: bool
    correct_index: int | None = None  # only after a pass, so answers cannot be harvested
    explanation: str
    new_progress_percent: float
    course_completed: bool
    score: float


class EnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: BodyDatabaseID
    course_id: BodyDatabaseID


class CourseAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: BodyDatabaseID
