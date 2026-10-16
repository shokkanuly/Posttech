from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceCitation(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    section_title: str
    snippet: str
    version: str
    is_synthetic: bool


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)


class AIChatResponse(BaseModel):
    question: str
    answer: str
    answer_status: Literal["grounded", "fallback", "unauthorized"]
    sources: list[SourceCitation] = Field(default_factory=list)
    escalation_guidance: str | None = None
    processing_time_ms: float


class KnowledgeSourceResponse(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    section_title: str
    content: str
    version: str
    is_synthetic: bool
