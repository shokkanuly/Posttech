from typing import List, Optional
from pydantic import BaseModel


class SourceCitation(BaseModel):
    document_title: str
    section_title: str
    snippet: str
    version: str = "1.0 (Approved)"


class AIChatRequest(BaseModel):
    question: str


class AIChatResponse(BaseModel):
    question: str
    answer: str
    answer_status: str  # "grounded", "fallback", "unauthorized", "ambiguous"
    sources: List[SourceCitation] = []
    escalation_guidance: Optional[str] = None
    processing_time_ms: float
