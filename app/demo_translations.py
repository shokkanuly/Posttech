"""Install reviewed translations for exact, known synthetic fixtures only."""

from datetime import datetime, timezone

from app.localization import CATALOG
from app.models.knowledge import KnowledgeDocument
from app.services.audit_service import audit_service


def install_demo_translations(db) -> None:
    for doc in db.query(KnowledgeDocument).filter_by(is_synthetic=True, is_approved=True).all():
        # Never translate arbitrary uploaded policies or overwrite authored translations.
        if doc.language != "en" or doc.translations:
            continue
        fields = {"title": doc.title, "category": doc.category, "description": doc.description}
        if any(value and value not in CATALOG["messages"] for value in fields.values()):
            continue
        if not doc.chunks or any(
            chunk.content not in CATALOG["messages"]
            or chunk.section_title not in CATALOG["messages"]
            for chunk in doc.chunks
        ):
            continue
        doc.translations = {
            language: {
                key: CATALOG["messages"][value][language] if value else value
                for key, value in fields.items()
            }
            for language in ("ru", "kk")
        }
        for chunk in doc.chunks:
            chunk.translations = {
                language: {
                    key: CATALOG["messages"][getattr(chunk, key)][language]
                    for key in ("section_title", "content")
                }
                for language in ("ru", "kk")
            }
        doc.revision += 1
        doc.updated_at = datetime.now(timezone.utc)
        audit_service.log_event(
            db,
            action="KNOWLEDGE_DEMO_LOCALIZED",
            actor_id=doc.approved_by_id,
            target_type="knowledge_document",
            target_id=str(doc.id),
            details={"languages": ["ru", "kk"], "revision": doc.revision, "synthetic": True},
        )
