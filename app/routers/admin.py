from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.models.audit import AuditEvent
from app.schemas.integration import AdapterTelemetry
from app.services.auth_service import require_role
from app.integrations.one_c_zup import one_c_adapter
from app.integrations.documentolog import documentolog_adapter

router = APIRouter(prefix="/admin", tags=["HR Administration"])


class KnowledgeChunkCreate(BaseModel):
    document_id: int
    section_title: str
    content: str
    tags: Optional[str] = None
    access_level: str = "all"


class KnowledgeChunkResponse(BaseModel):
    id: int
    document_title: str
    section_title: str
    content: str
    tags: Optional[str] = None
    access_level: str


@router.get("/knowledge", response_model=List[KnowledgeChunkResponse])
def get_admin_knowledge(
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    chunks = db.query(KnowledgeChunk).join(KnowledgeDocument).all()
    return [
        KnowledgeChunkResponse(
            id=c.id,
            document_title=c.document.title,
            section_title=c.section_title,
            content=c.content,
            tags=c.tags,
            access_level=c.access_level,
        )
        for c in chunks
    ]


@router.post("/knowledge", response_model=KnowledgeChunkResponse, status_code=201)
def add_admin_knowledge_chunk(
    payload: KnowledgeChunkCreate,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == payload.document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    chunk = KnowledgeChunk(
        document_id=payload.document_id,
        section_title=payload.section_title,
        content=payload.content,
        tags=payload.tags,
        access_level=payload.access_level,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    return KnowledgeChunkResponse(
        id=chunk.id,
        document_title=doc.title,
        section_title=chunk.section_title,
        content=chunk.content,
        tags=chunk.tags,
        access_level=chunk.access_level,
    )


@router.get("/integrations", response_model=List[AdapterTelemetry])
def get_admin_integrations(
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
):
    return [
        one_c_adapter.get_telemetry(),
        documentolog_adapter.get_telemetry(),
    ]


@router.get("/audit")
def get_audit_trail(
    limit: int = 50,
    current_user: User = Depends(require_role(UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor_id": e.actor_id,
            "actor_name": e.actor.full_name if e.actor else "Anonymous",
            "target_type": e.target_type,
            "target_id": e.target_id,
            "details": e.details_json,
            "ip_address": e.ip_address,
            "timestamp": e.created_at.isoformat(),
        }
        for e in events
    ]
