from typing import List

from fastapi import APIRouter, Depends
from fastapi import Request as FastAPIRequest
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.localization import Language, LocalizedRoute, current_language, document_text
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.pagination import Page
from app.schemas.ai import AIChatRequest, AIChatResponse, KnowledgeSourceResponse
from app.schemas.common import DatabaseID
from app.schemas.knowledge import KnowledgeDocumentSummary
from app.services.ai_service import ai_service
from app.services.auth_service import get_current_user

router = APIRouter(route_class=LocalizedRoute, prefix="/ai", tags=["AI Jana Assistant"])


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
    chunk_id: DatabaseID,
    revision: DatabaseID | None = None,
    language: Language | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ai_service.source(db, chunk_id, current_user.role, revision, language)


@router.get("/documents", response_model=list[KnowledgeDocumentSummary])
def get_documents(
    page: Page, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    query = (
        db.query(KnowledgeDocument)
        .join(KnowledgeChunk)
        .filter(KnowledgeDocument.is_active.is_(True), KnowledgeDocument.is_approved.is_(True))
    )
    if current_user.role != UserRole.HR_ADMIN:
        query = query.filter(KnowledgeChunk.access_level.in_(["all", current_user.role.value]))
    language = current_language.get()
    query = query.filter(
        or_(
            KnowledgeDocument.language == language,
            KnowledgeDocument.translations[language].as_string().is_not(None),
        ),
        or_(
            KnowledgeDocument.language == language,
            KnowledgeChunk.translations[language].as_string().is_not(None),
        ),
    )
    # DISTINCT on ids, not whole rows: PostgreSQL cannot compare JSON columns.
    visible_ids = query.with_entities(KnowledgeDocument.id).distinct()
    documents = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.id.in_(visible_ids))
        .order_by(KnowledgeDocument.id)
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return [
        KnowledgeDocumentSummary(
            id=d.id, title=document_text(d)["title"], version=d.version, is_synthetic=d.is_synthetic
        )
        for d in documents
    ]
