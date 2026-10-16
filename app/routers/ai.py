from typing import List

from fastapi import APIRouter, Depends
from fastapi import Request as FastAPIRequest
from pydantic import PositiveInt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.ai import AIChatRequest, AIChatResponse, KnowledgeSourceResponse
from app.schemas.knowledge import KnowledgeDocumentSummary
from app.services.ai_service import ai_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/ai", tags=["AI Jana Assistant"])


@router.post("/chat", response_model=AIChatResponse)
def ask_ai_jana(
    payload: AIChatRequest,
    request: FastAPIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ip_addr = request.client.host if request.client else None
    return ai_service.process_chat_query(
        db=db,
        user=current_user,
        payload=payload,
        ip_address=ip_addr,
    )


@router.get("/suggestions", response_model=List[str])
def get_prompt_suggestions(current_user: User = Depends(get_current_user)):
    return [
        "How do I request vacation?",
        "Where can I find my leave balance?",
        "What is the advance payment policy?",
        "What are the official Jana Post working hours?",
        "How do I contact HR for special requests?",
        "What is the pet insurance policy?",  # Demo for safe fallback
    ]


@router.get("/sources/{chunk_id}", response_model=KnowledgeSourceResponse)
def get_source(
    chunk_id: PositiveInt,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ai_service.source(db, chunk_id, current_user.role)


@router.get("/documents", response_model=list[KnowledgeDocumentSummary])
def get_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = {
        chunk.document.id: chunk.document
        for chunk in ai_service.accessible_chunks(db, current_user.role).all()
    }
    return [
        KnowledgeDocumentSummary(
            id=d.id, title=d.title, version=d.version, is_synthetic=d.is_synthetic
        )
        for d in documents.values()
    ]
