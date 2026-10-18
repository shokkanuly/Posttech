from datetime import datetime, timezone
from typing import cast

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.localization import document_text, source_text
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
                "revision",
                "is_active",
                "is_approved",
                "is_synthetic",
                "approved_by_id",
                "approved_at",
                "updated_at",
                "language",
                "translations",
                "policy_key",
                "priority",
                "effective_from",
                "effective_until",
                "known_conflict",
            )
        } | document_text(doc)

    @staticmethod
    def serialize_chunk(chunk):
        localized = source_text(chunk)
        return KnowledgeChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            document_title=localized["document_title"]
            if localized
            else document_text(chunk.document)["title"],
            section_title=localized["section_title"] if localized else chunk.section_title,
            content=localized["content"] if localized else chunk.content,
            tags=chunk.tags,
            access_level=chunk.access_level,
            is_approved=chunk.document.is_approved,
            is_synthetic=chunk.document.is_synthetic,
            document_revision=chunk.document.revision,
            language=localized["language"] if localized else chunk.document.language,
            translations=chunk.translations,
        )

    @staticmethod
    def invalidate(doc):
        doc.is_approved = False
        doc.approved_by_id = None
        doc.approved_at = None
        doc.updated_at = datetime.now(timezone.utc)

    @classmethod
    def prepare_change(cls, db: Session, document_id: int, expected_revision: int | None):
        """Serialize source changes and approvals through their shared parent row."""
        statement = update(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        if expected_revision is not None:
            statement = statement.where(KnowledgeDocument.revision == expected_revision)
        result = db.execute(
            statement.values(
                revision=KnowledgeDocument.revision + 1,
                is_approved=False,
                approved_by_id=None,
                approved_at=None,
                updated_at=datetime.now(timezone.utc),
            ),
            execution_options={"synchronize_session": False},
        )
        if cast(CursorResult, result).rowcount != 1:
            db.rollback()
            cls.document(db, document_id)  # Missing rows still return 404.
            raise HTTPException(409, "Document changed; reload and review the current revision")
        doc = cls.document(db, document_id)
        db.refresh(doc)
        db.expire(doc, ["chunks"])
        return doc

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
        result = cls.serialize_document(doc)
        db.commit()
        return result

    @classmethod
    def update_document(cls, db, document_id, payload, actor):
        changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if not changes or any(
            v is None
            and k not in {"description", "policy_key", "effective_from", "effective_until"}
            for k, v in changes.items()
        ):
            raise HTTPException(422, "Provide non-null document changes")
        doc = cls.prepare_change(db, document_id, payload.expected_revision)
        approved = changes.pop("is_approved", False)
        if {
            "title",
            "category",
            "description",
            "language",
        } & changes.keys() and "translations" not in changes:
            doc.translations = {}
        for key, value in changes.items():
            setattr(doc, key, value)
        if doc.effective_from and doc.effective_until and doc.effective_from > doc.effective_until:
            raise HTTPException(422, "Invalid policy effective period")
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
            details={
                "approved": doc.is_approved,
                "fields": sorted(changes),
                "revision": doc.revision,
            },
        )
        db.flush()
        result = cls.serialize_document(doc)
        db.commit()
        return result

    @classmethod
    def create_chunk(cls, db, payload, actor):
        doc = cls.prepare_change(db, payload.document_id, payload.expected_revision)
        chunk = KnowledgeChunk(**payload.model_dump(exclude={"expected_revision"}))
        db.add(chunk)
        db.flush()
        audit_service.log_event(
            db,
            action="KNOWLEDGE_CHUNK_CREATED",
            actor_id=actor.id,
            target_type="knowledge_chunk",
            target_id=str(chunk.id),
            details={"document_id": doc.id, "revision": doc.revision},
        )
        result = cls.serialize_chunk(chunk)
        db.commit()
        return result

    @classmethod
    def update_chunk(cls, db, chunk_id, payload, actor):
        chunk = db.get(KnowledgeChunk, chunk_id)
        if not chunk:
            raise HTTPException(404, "Knowledge source not found")
        changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if not changes or any(v is None and k != "tags" for k, v in changes.items()):
            raise HTTPException(422, "Provide non-null source changes")
        doc = cls.prepare_change(db, chunk.document_id, payload.expected_revision)
        db.refresh(chunk)
        if {"section_title", "content"} & changes.keys() and "translations" not in changes:
            chunk.translations = {}
        for key, value in changes.items():
            setattr(chunk, key, value)
        audit_service.log_event(
            db,
            action="KNOWLEDGE_CHUNK_UPDATED",
            actor_id=actor.id,
            target_type="knowledge_chunk",
            target_id=str(chunk.id),
            details={"fields": sorted(changes), "document_id": doc.id, "revision": doc.revision},
        )
        db.flush()
        result = cls.serialize_chunk(chunk)
        db.commit()
        return result


knowledge_service = KnowledgeService()
