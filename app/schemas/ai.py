from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceCitation(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    section_title: str
    snippet: str
    version: str
    document_revision: int
    language: str
    is_synthetic: bool
    relevance: float | None = None  # TF-IDF similarity to the question, 0..1


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)


class AIChatResponse(BaseModel):
    question: str
    answer: str
    answer_status: Literal["grounded", "fallback", "unauthorized"]
    sources: list[SourceCitation] = Field(default_factory=list)
    escalation_guidance: str | None = None
    engine: str = "extractive"  # or "gemini:<model>" when a verified model answer is shown
    processing_time_ms: float
    language: str = "en"


class KnowledgeSourceResponse(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    section_title: str
    content: str
    version: str
    document_revision: int
    language: str
    is_synthetic: bool
