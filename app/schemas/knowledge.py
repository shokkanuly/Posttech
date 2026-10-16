from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import UTCDateTime

AccessLevel = Literal["all", "employee", "manager", "hr_admin"]


class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=255)
    category: str = Field(default="HR Policy", min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    version: str = Field(default="1.0", min_length=1, max_length=20)
    is_synthetic: bool = False


class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    version: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None
    is_approved: bool | None = None


class KnowledgeChunkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    document_id: int = Field(gt=0)
    section_title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    tags: str | None = Field(default=None, max_length=255)
    access_level: AccessLevel = "all"


class KnowledgeChunkPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    section_title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    tags: str | None = Field(default=None, max_length=255)
    access_level: AccessLevel | None = None


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


class KnowledgeDocumentResponse(BaseModel):
    id: int
    title: str
    category: str
    description: str | None
    version: str
    is_active: bool
    is_approved: bool
    is_synthetic: bool
    approved_by_id: int | None
    approved_at: UTCDateTime | None
    updated_at: UTCDateTime


class KnowledgeDocumentSummary(BaseModel):
    id: int
    title: str
    version: str
    is_synthetic: bool
