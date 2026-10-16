from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import KnowledgeChunkResponse
from app.services.audit_service import audit_service


class KnowledgeService:
    @staticmethod
    def document(db: Session, document_id: int):
        doc = db.get(KnowledgeDocument, document_id)
        if not doc:
            raise HTTPException(404, "Knowledge document not found")
        return doc

    @staticmethod
    def serialize_document(doc):
        return {
            field: getattr(doc, field)
            for field in (
                "id",
                "title",
                "category",
                "description",
                "version",
                "is_active",
                "is_approved",
                "is_synthetic",
                "approved_by_id",
                "approved_at",
                "updated_at",
            )
        }

    @staticmethod
    def serialize_chunk(chunk):
        return KnowledgeChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            document_title=chunk.document.title,
            section_title=chunk.section_title,
            content=chunk.content,
            tags=chunk.tags,
            access_level=chunk.access_level,
            is_approved=chunk.document.is_approved,
            is_synthetic=chunk.document.is_synthetic,
        )

    @staticmethod
    def invalidate(doc):
        doc.is_approved = False
        doc.approved_by_id = None
        doc.approved_at = None
        doc.updated_at = datetime.now(timezone.utc)

    @classmethod
    def create_document(cls, db, payload, actor):
        doc = KnowledgeDocument(**payload.model_dump())
        db.add(doc)
        db.flush()
        audit_service.log_event(
            db,
            action="KNOWLEDGE_DOCUMENT_CREATED",
            actor_id=actor.id,
            target_type="knowledge_document",
            target_id=str(doc.id),
        )
        db.commit()
        return cls.serialize_document(doc)

    @classmethod
    def update_document(cls, db, document_id, payload, actor):
        doc = cls.document(db, document_id)
        changes = payload.model_dump(exclude_unset=True)
        if not changes or any(v is None and k != "description" for k, v in changes.items()):
            raise HTTPException(422, "Provide non-null document changes")
        cls.invalidate(doc)
        approved = changes.pop("is_approved", False)
        for key, value in changes.items():
            setattr(doc, key, value)
        if approved:
            if not doc.is_active or not doc.chunks:
                raise HTTPException(
                    422, "An active document with source content is required for approval"
                )
            doc.is_approved = True
            doc.approved_by_id = actor.id
            doc.approved_at = datetime.now(timezone.utc)
        audit_service.log_event(
            db,
            action="KNOWLEDGE_DOCUMENT_UPDATED",
            actor_id=actor.id,
            target_type="knowledge_document",
            target_id=str(doc.id),
            details={"approved": doc.is_approved, "fields": sorted(changes)},
        )
        db.commit()
        return cls.serialize_document(doc)

    @classmethod
    def create_chunk(cls, db, payload, actor):
        doc = cls.document(db, payload.document_id)
        cls.invalidate(doc)
        chunk = KnowledgeChunk(**payload.model_dump())
        db.add(chunk)
        db.flush()
        audit_service.log_event(
            db,
            action="KNOWLEDGE_CHUNK_CREATED",
            actor_id=actor.id,
            target_type="knowledge_chunk",
            target_id=str(chunk.id),
        )
        db.commit()
        return cls.serialize_chunk(chunk)

    @classmethod
    def update_chunk(cls, db, chunk_id, payload, actor):
        chunk = db.get(KnowledgeChunk, chunk_id)
        if not chunk:
            raise HTTPException(404, "Knowledge source not found")
        changes = payload.model_dump(exclude_unset=True)
        if not changes or any(v is None and k != "tags" for k, v in changes.items()):
            raise HTTPException(422, "Provide non-null source changes")
        cls.invalidate(chunk.document)
        for key, value in changes.items():
            setattr(chunk, key, value)
        audit_service.log_event(
            db,
            action="KNOWLEDGE_CHUNK_UPDATED",
            actor_id=actor.id,
            target_type="knowledge_chunk",
            target_id=str(chunk.id),
            details={"fields": sorted(changes)},
        )
        db.commit()
        return cls.serialize_chunk(chunk)


knowledge_service = KnowledgeService()
