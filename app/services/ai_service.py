"""Conservative extractive retrieval. No employee records, model calls, or invented sources."""

import hashlib
import re
import time
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session, contains_eager

from app.config import settings
from app.localization import Language, current_language, source_text, translate
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.schemas.ai import AIChatRequest, AIChatResponse, SourceCitation
from app.services.audit_service import audit_service


class AIService:
    PRIVACY_RESTRICTED_TERMS = (
        "salary of",
        "зарплат",
        "оклад",
        "зарабатыва",
        "сколько получает",
        "айлық",
        "жалақы",
        "who got fired",
        "кого уволили",
        "personal phone",
        "личный телефон",
        "жеке телефон",
        "confidential",
        "паспортные данные",
        "жеке куәлік",
        "terminate employee",
        "уволить сотрудника",
        "disciplinary record",
        "home address",
        "medical record",
        "жалақысын",
        "личные данные коллег",
        "домашний адрес",
        "әріптестің",
    )
    STOP_WORDS = set(
        (
            "what the for with from how does can are and this that policy rules about guide sample "
            "where find many get official jana post system please tell explain employees employee "
            "should must would could my your their its into do is has have not which when why "
            "что как для или это где правила инструкция қалай қандай қайда туралы ереже"
        ).split()
    )
    ALIASES = {
        "vacations": "vacation",
        "holidays": "vacation",
        "requests": "request",
        "requesting": "request",
        "hours": "hour",
        "days": "day",
        "balances": "balance",
        "payments": "payment",
        "contacts": "contact",
        **dict.fromkeys(
            (
                "отпуск",
                "отпуска",
                "отпуске",
                "отпуску",
                "демалыс",
                "демалысқа",
                "демалысының",
                "демалысқа",
            ),
            "vacation",
        ),
        **dict.fromkeys(
            (
                "заявка",
                "заявку",
                "заявки",
                "заявок",
                "подать",
                "запросить",
                "өтініш",
                "өтінішті",
                "өтініштер",
                "беремін",
                "сұраймын",
                "сұрау",
                "оформить",
                "оформление",
                "взять",
                "получить",
            ),
            "request",
        ),
        **dict.fromkeys(
            ("остаток", "остатка", "баланс", "қалдық", "қалдығы", "қалдығын", "қалдықтан"),
            "balance",
        ),
        **dict.fromkeys(
            ("день", "дней", "дня", "дни", "күн", "күндерінің", "күндер", "күндері"), "day"
        ),
        **dict.fromkeys(("аванс", "аванса", "авансқа", "авансты"), "advance"),
        **dict.fromkeys(("график", "графика", "кесте", "кестесі", "кестеде"), "schedule"),
        **dict.fromkeys(("рабочее", "работы", "работа", "жұмыс", "working"), "work"),
        **dict.fromkeys(
            ("кадровую", "кадровая", "кадровой", "кадр", "кадры", "службу", "қызметі"), "hr"
        ),
        **dict.fromkeys(("контакты", "связаться", "байланыс"), "contact"),
    }
    STOP_WORDS |= set(
        "подскажите какой какая какие как где посмотреть системе мой мои мне туралы қалай қандай қайдан көремін жүйеде есть могу можно для нужно "
        "положено делать если отдел когда істеймін қашан мен".split()
    )
    # ponytail: RU/KK inflect heavily, so Cyrillic words match on a 5-letter prefix
    # (отпуском ~ отпуска). Swap for a Snowball stemmer if false matches show up.
    ALIASES |= {k[:5]: v for k, v in ALIASES.items() if not k.isascii()}
    STOP_WORDS |= {w[:5] for w in STOP_WORDS if not w.isascii()}

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        text = text.lower().replace("time off", "vacation").replace("carry over", "carryover")
        tokens = set()
        for t in re.findall(r"\w+", text):
            stem = t if t.isascii() or t in cls.ALIASES else t[:5]
            if len(t) > 2 and t not in cls.STOP_WORDS and stem not in cls.STOP_WORDS:
                tokens.add(cls.ALIASES.get(stem, stem))
        return tokens

    @staticmethod
    def accessible_chunks(db: Session, role: UserRole):
        query = (
            db.query(KnowledgeChunk)
            .join(KnowledgeDocument)
            .options(contains_eager(KnowledgeChunk.document))
            .filter(KnowledgeDocument.is_active.is_(True), KnowledgeDocument.is_approved.is_(True))
        )
        if role != UserRole.HR_ADMIN:
            query = query.filter(KnowledgeChunk.access_level.in_(["all", role.value]))
        return query

    @classmethod
    def retrieve_relevant_chunks(cls, db: Session, question: str, user_role: UserRole):
        tokens = cls._tokenize(question)
        if not tokens:
            return []
        ranked = []
        for chunk in cls.accessible_chunks(db, user_role).yield_per(100):
            if source_text(chunk) is None:
                continue
            # Match the question in any reviewed language; the answer stays in the reader's.
            texts = [source_text(chunk, language) for language in ("en", "ru", "kk")]
            # Exact token coverage, not substring counts or repeated keyword sums.
            evidence = cls._tokenize(
                " ".join(f"{t['section_title']} {t['content']}" for t in texts if t)
                + f" {chunk.tags or ''}"
            )
            score = len(tokens & evidence) / len(tokens)
            if score >= settings.AI_CONFIDENCE_THRESHOLD:
                ranked.append((chunk, score))
                ranked = sorted(ranked, key=lambda item: (-item[1], item[0].id))[:2]
        return sorted(ranked, key=lambda item: (-item[1], item[0].id))

    @classmethod
    def source(
        cls,
        db: Session,
        chunk_id: int,
        role: UserRole,
        revision: int | None = None,
        language: Language | None = None,
    ):
        chunk = cls.accessible_chunks(db, role).filter(KnowledgeChunk.id == chunk_id).first()
        if not chunk:
            raise HTTPException(404, "Approved knowledge source not found")
        localized = source_text(chunk, language)
        if localized is None:
            raise HTTPException(404, "Approved knowledge source not found")
        if revision is not None and chunk.document.revision != revision:
            raise HTTPException(
                409, "Source changed; ask the question again for a current citation"
            )
        return {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            **localized,
            "version": chunk.document.version,
            "document_revision": chunk.document.revision,
            "is_synthetic": chunk.document.is_synthetic,
        }

    @classmethod
    def process_chat_query(
        cls, db: Session, user: User, payload: AIChatRequest, ip_address=None
    ) -> AIChatResponse:
        started = time.monotonic()
        question = payload.question
        guidance = translate(f"Contact HR support at {settings.HR_SUPPORT_EMAIL} for confirmation.")
        answer_status: Literal["grounded", "fallback", "unauthorized"]
        chunks = []
        views = []
        if any(term in question.lower() for term in cls.PRIVACY_RESTRICTED_TERMS):
            answer_status = "unauthorized"
            answer = translate(
                "AI Jana protects employee privacy. Individual salaries, disciplinary and private employee "
                "records are not available through knowledge queries. Check your own profile or contact HR."
            )
        else:
            matches = cls.retrieve_relevant_chunks(db, question, user.role)
            chunks = [chunk for chunk, _score in matches[:2]]
            views = [(chunk, text) for chunk in chunks if (text := source_text(chunk)) is not None]
            answer_status = "grounded" if chunks else "fallback"
            answer = (
                translate(
                    "I couldn't find a reliable answer to this question in the approved knowledge base."
                )
                + " "
                + guidance
            )
            if chunks:
                answer = "\n\n".join(
                    f"{translate('Synthetic example; not official HR policy.') + ' ' if c.document.is_synthetic else ''}"
                    f"{translate('Source:')} {text['document_title']} — {text['section_title']} (v{c.document.version})\n{text['content']}"
                    for c, text in views
                )
        sources = [
            SourceCitation(
                chunk_id=c.id,
                document_id=c.document_id,
                document_title=text["document_title"],
                section_title=text["section_title"],
                snippet=text["content"][:220],
                version=c.document.version,
                document_revision=c.document.revision,
                is_synthetic=c.document.is_synthetic,
                language=current_language.get(),
            )
            for c, text in views
        ]
        action = {
            "grounded": "AI_QUERY_GROUNDED_ANSWER",
            "fallback": "AI_QUERY_FALLBACK",
            "unauthorized": "AI_QUERY_PRIVACY_BLOCKED",
        }[answer_status]
        audit_service.log_event(
            db,
            action=action,
            actor_id=user.id,
            target_type="ai_chat",
            details={
                "question_hash": hashlib.sha256(question.encode()).hexdigest(),
                "status": answer_status,
                "source_ids": [c.id for c in chunks],
                "source_revisions": [
                    {
                        "chunk_id": c.id,
                        "document_revision": c.document.revision,
                        "content_hash": hashlib.sha256(text["content"].encode()).hexdigest(),
                        "language": current_language.get(),
                    }
                    for c, text in views
                ],
            },
        )
        db.commit()
        return AIChatResponse(
            question=question,
            answer=answer,
            answer_status=answer_status,
            sources=sources,
            escalation_guidance=guidance,
            processing_time_ms=round((time.monotonic() - started) * 1000, 2),
        )


ai_service = AIService()
