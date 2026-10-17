"""Validate file-based HR sources and import them as drafts in one transaction."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.localization import Language
from app.models.audit import AuditEvent
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.schemas.knowledge import AccessLevel, DocumentCreate, SourceTranslation
from app.services.audit_service import audit_service


class FileSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,60}$")
    section_title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=20000)
    tags: str | None = Field(default=None, max_length=255)
    access_level: AccessLevel = "all"
    translations: dict[Language, SourceTranslation] = Field(default_factory=dict)


class PolicyBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    schema_version: Literal[1]
    bundle_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,80}$")
    kind: Literal["document", "template"] = "document"
    provenance: str = Field(min_length=1, max_length=1000)
    document: DocumentCreate
    sections: list[FileSection] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def check_sources(self):
        if len({section.key for section in self.sections}) != len(self.sections):
            raise ValueError("Section keys must be unique within a bundle")
        languages = set(self.document.translations)
        if self.document.language in languages:
            raise ValueError("Primary language must not be duplicated in translations")
        if any(set(section.translations) != languages for section in self.sections):
            raise ValueError("Every section must have the same translations as its document")
        return self

    def fingerprint(self) -> str:
        value = json.dumps(self.model_dump(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(value.encode()).hexdigest()


def read_bundle(path: Path) -> PolicyBundle:
    if path.stat().st_size > 1_048_576:
        raise ValueError("Knowledge files must not exceed 1 MiB")
    return PolicyBundle.model_validate_json(path.read_text(encoding="utf-8"))


def import_bundle(db: Session, bundle: PolicyBundle, actor: User) -> dict:
    if not actor.is_active or actor.role != UserRole.HR_ADMIN:
        raise HTTPException(403, "An active HR administrator is required")
    if bundle.kind == "template":
        raise ValueError("Fill the template and change kind to document before importing")
    if any(
        marker in json.dumps(bundle.model_dump(), ensure_ascii=False)
        for marker in ("ЗАПОЛНИТЬ:", "ТОЛТЫРУ:")
    ):
        raise ValueError("Remove template placeholders before importing a document")
    # details_json is plain text: match the bundle in Python so SQLite and PostgreSQL agree.
    previous = next(
        (
            event
            for event in db.query(AuditEvent)
            .filter(AuditEvent.action == "KNOWLEDGE_FILE_IMPORTED")
            .order_by(AuditEvent.id)
            if json.loads(event.details_json or "{}").get("bundle_id") == bundle.bundle_id
        ),
        None,
    )
    if previous:
        details = json.loads(previous.details_json or "{}")
        if details.get("sha256") != bundle.fingerprint():
            raise ValueError("This bundle ID already exists; use a new ID/version for new content")
        if not previous.target_id or not db.get(KnowledgeDocument, int(previous.target_id)):
            raise ValueError(
                "Previously imported document is missing; review before importing again"
            )
        return {"document_id": int(previous.target_id), "created": False}
    if (
        db.query(KnowledgeDocument)
        .filter_by(
            title=bundle.document.title,
            version=bundle.document.version,
            language=bundle.document.language,
        )
        .first()
    ):
        raise ValueError("A document with this title, language and version already exists")
    try:
        document = KnowledgeDocument(**bundle.document.model_dump(), is_approved=False)
        db.add(document)
        db.flush()
        for section in bundle.sections:
            db.add(KnowledgeChunk(document_id=document.id, **section.model_dump(exclude={"key"})))
        audit_service.log_event(
            db,
            action="KNOWLEDGE_FILE_IMPORTED",
            actor_id=actor.id,
            target_type="knowledge_document",
            target_id=str(document.id),
            details={"bundle_id": bundle.bundle_id, "sha256": bundle.fingerprint()},
        )
        document_id = document.id
        db.commit()
        return {"document_id": document_id, "created": True}
    except Exception:
        db.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка и импорт кадровых файлов как черновиков")
    parser.add_argument("command", choices=["validate", "import"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--actor-email", help="Адрес действующего HR-администратора для импорта")
    args = parser.parse_args()
    try:
        bundle = read_bundle(args.file)
        if args.command == "validate":
            print(json.dumps({"valid": True, "bundle_id": bundle.bundle_id, "kind": bundle.kind}))
            return
        if not args.actor_email:
            parser.error("Для импорта укажите --actor-email")
        from app.database import SessionLocal, engine
        from app.migrate import require_current_schema

        require_current_schema(engine)
        with SessionLocal() as db:
            actor = db.query(User).filter_by(email=args.actor_email.lower()).first()
            if not actor:
                raise ValueError("HR administrator account not found")
            print(json.dumps(import_bundle(db, bundle, actor)))
    except ValidationError as exc:
        parser.exit(1, json.dumps(exc.errors(include_input=False, include_context=False)) + "\n")
    except (ValueError, OSError, HTTPException) as exc:
        message = exc.detail if isinstance(exc, HTTPException) else str(exc)
        parser.exit(1, f"Ошибка: {message}\n")


if __name__ == "__main__":
    main()
