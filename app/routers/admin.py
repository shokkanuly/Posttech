from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.database import get_db
from app.integrations.documentolog import documentolog_adapter
from app.integrations.one_c_zup import one_c_adapter
from app.localization import LocalizedRoute
from app.models.audit import AuditEvent
from app.models.enums import RequestStatus, UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.request import Request
from app.models.user import User
from app.pagination import Page
from app.schemas.academy import CourseDetailResponse, EnrollmentCreate
from app.schemas.common import AdminSummaryResponse, AuditResponse, DatabaseID
from app.schemas.integration import AdapterTelemetry
from app.schemas.knowledge import (
    DocumentCreate,
    DocumentPatch,
    KnowledgeChunkCreate,
    KnowledgeChunkPatch,
    KnowledgeChunkResponse,
    KnowledgeDocumentResponse,
)
from app.services.academy_service import academy_service
from app.services.auth_service import require_role
from app.services.knowledge_service import knowledge_service

router = APIRouter(route_class=LocalizedRoute, prefix="/admin", tags=["HR Administration"])
admin = require_role(UserRole.HR_ADMIN)


@router.get("/knowledge/documents", response_model=list[KnowledgeDocumentResponse])
def list_documents(page: Page, current_user: User = Depends(admin), db: Session = Depends(get_db)):
    return [
        knowledge_service.serialize_document(d)
        for d in db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.id)
        .offset(page.offset)
        .limit(page.limit)
        .all()
    ]


@router.post("/knowledge/documents", status_code=201, response_model=KnowledgeDocumentResponse)
def create_document(
    payload: DocumentCreate, current_user: User = Depends(admin), db: Session = Depends(get_db)
):
    return knowledge_service.create_document(db, payload, current_user)


@router.patch("/knowledge/documents/{document_id}", response_model=KnowledgeDocumentResponse)
def update_document(
    document_id: DatabaseID,
    payload: DocumentPatch,
    current_user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    return knowledge_service.update_document(db, document_id, payload, current_user)


@router.get("/knowledge", response_model=list[KnowledgeChunkResponse])
def get_admin_knowledge(
    page: Page, current_user: User = Depends(admin), db: Session = Depends(get_db)
):
    return [
        knowledge_service.serialize_chunk(c)
        for c in db.query(KnowledgeChunk)
        .join(KnowledgeDocument)
        .options(contains_eager(KnowledgeChunk.document))
        .order_by(KnowledgeChunk.id)
        .offset(page.offset)
        .limit(page.limit)
        .all()
    ]


@router.post("/knowledge", response_model=KnowledgeChunkResponse, status_code=201)
def add_admin_knowledge_chunk(
    payload: KnowledgeChunkCreate,
    current_user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    return knowledge_service.create_chunk(db, payload, current_user)


@router.patch("/knowledge/{chunk_id}", response_model=KnowledgeChunkResponse)
def update_chunk(
    chunk_id: DatabaseID,
    payload: KnowledgeChunkPatch,
    current_user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    return knowledge_service.update_chunk(db, chunk_id, payload, current_user)


@router.post("/enrollments", response_model=CourseDetailResponse)
def assign_course(
    payload: EnrollmentCreate, current_user: User = Depends(admin), db: Session = Depends(get_db)
):
    return academy_service.enroll(db, payload.user_id, payload.course_id, current_user.id)


@router.get("/integrations", response_model=list[AdapterTelemetry])
def get_admin_integrations(current_user: User = Depends(admin)):
    return [one_c_adapter.get_telemetry(), documentolog_adapter.get_telemetry()]


@router.get("/audit", response_model=list[AuditResponse])
def get_audit_trail(
    page: Page,
    current_user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    events = (
        db.query(AuditEvent)
        .options(joinedload(AuditEvent.actor))  # one query, not one per row
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor_id": e.actor_id,
            "actor_name": e.actor.full_name if e.actor else "Anonymous",
            "target_type": e.target_type,
            "target_id": e.target_id,
            "details": e.details_json,
            "timestamp": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/summary", response_model=AdminSummaryResponse)
def admin_summary(current_user: User = Depends(admin), db: Session = Depends(get_db)):
    return AdminSummaryResponse(
        active_accounts=db.query(User).filter(User.is_active.is_(True)).count(),
        pending_requests=db.query(Request).filter(Request.status == RequestStatus.PENDING).count(),
        knowledge_chunks=db.query(KnowledgeChunk).count(),
    )
