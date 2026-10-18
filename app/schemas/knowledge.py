from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.localization import Language
from app.schemas.common import BodyDatabaseID, UTCDateTime

AccessLevel = Literal["all", "employee", "manager", "hr_admin"]


class DocumentTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(default="HR Policy", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class SourceTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    section_title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(default="HR Policy", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    version: str = Field(default="1.0", min_length=1, max_length=20)
    is_synthetic: StrictBool = False
    language: Language = "en"
    translations: dict[Language, DocumentTranslation] = Field(default_factory=dict)
    policy_key: str | None = Field(default=None, min_length=1, max_length=100)
    priority: int = Field(default=0, ge=-100, le=100, strict=True)
    effective_from: date | None = None
    effective_until: date | None = None
    known_conflict: StrictBool = False

    @model_validator(mode="after")
    def valid_period(self):
        if (
            self.effective_from
            and self.effective_until
            and self.effective_from > self.effective_until
        ):
            raise ValueError("Invalid policy effective period")
        return self


class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: StrictBool | None = None
    is_approved: StrictBool | None = None
    expected_revision: BodyDatabaseID | None = None
    language: Language | None = None
    translations: dict[Language, DocumentTranslation] | None = None
    policy_key: str | None = Field(default=None, min_length=1, max_length=100)
    priority: int | None = Field(default=None, ge=-100, le=100, strict=True)
    effective_from: date | None = None
    effective_until: date | None = None
    known_conflict: StrictBool | None = None

    @model_validator(mode="after")
    def require_reviewed_revision(self):
        if self.is_approved is True and self.expected_revision is None:
            raise ValueError("Approval requires the expected_revision of the reviewed document")
        return self


class KnowledgeChunkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: BodyDatabaseID
    expected_revision: BodyDatabaseID | None = None
    section_title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    tags: str | None = Field(default=None, max_length=255)
    access_level: AccessLevel = "all"
    translations: dict[Language, SourceTranslation] = Field(default_factory=dict)


class KnowledgeChunkPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    section_title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    tags: str | None = Field(default=None, max_length=255)
    access_level: AccessLevel | None = None
    expected_revision: BodyDatabaseID | None = None
    translations: dict[Language, SourceTranslation] | None = None


class KnowledgeChunkResponse(BaseModel):
    id: int
    document_id: int
    document_title: str
    section_title: str
    content: str
    tags: str | None = None
    access_level: AccessLevel
    is_approved: bool
    is_synthetic: bool
    document_revision: int
    language: str
    translations: dict[Language, SourceTranslation]


class KnowledgeDocumentResponse(BaseModel):
    id: int
    title: str
    category: str
    description: str | None
    version: str
    revision: int
    is_active: bool
    is_approved: bool
    is_synthetic: bool
    approved_by_id: int | None
    approved_at: UTCDateTime | None
    updated_at: UTCDateTime
    language: str
    translations: dict[Language, DocumentTranslation]
    policy_key: str | None
    priority: int
    effective_from: date | None
    effective_until: date | None
    known_conflict: bool


class KnowledgeDocumentSummary(BaseModel):
    id: int
    title: str
    version: str
    is_synthetic: bool
