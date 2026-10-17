"""AI Jana: privacy guard → ML retrieval → optional Gemini phrasing → source verification.

Only approved knowledge passages are retrieved. Local employee names are used only by
the privacy guard. Gemini can select exact source quotes; unsupported generated prose
is rejected in favour of an extractive answer or safe fallback.
"""

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session, contains_eager

from app.ai_rules import is_private_text, load_assistant_rules
from app.config import settings
from app.integrations import gemini
from app.localization import Language, current_language, source_text, translate
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.retrieval_ranker import load_relevance_model, relevance_features
from app.schemas.ai import AIChatRequest, AIChatResponse, SourceCitation
from app.services import ml_retrieval
from app.services.audit_service import audit_service

# ponytail: Latin→Cyrillic first-pass transliteration, enough to match seeded names
# (Timur → тимур) in Russian questions. Use a name-alias table for real HR data.
_TRANSLIT = (
    ("zh", "ж"),
    ("sh", "ш"),
    ("ch", "ч"),
    ("kh", "х"),
    ("ya", "я"),
    ("yu", "ю"),
    ("a", "а"),
    ("b", "б"),
    ("c", "к"),
    ("d", "д"),
    ("e", "е"),
    ("f", "ф"),
    ("g", "г"),
    ("h", "х"),
    ("i", "и"),
    ("j", "ж"),
    ("k", "к"),
    ("l", "л"),
    ("m", "м"),
    ("n", "н"),
    ("o", "о"),
    ("p", "п"),
    ("q", "к"),
    ("r", "р"),
    ("s", "с"),
    ("t", "т"),
    ("u", "у"),
    ("v", "в"),
    ("w", "у"),
    ("x", "кс"),
    ("y", "и"),
    ("z", "з"),
)


def _name_key(word: str) -> str:
    word = word.lower()
    for latin, cyrillic in _TRANSLIT:
        word = word.replace(latin, cyrillic)
    return word.replace("й", "и").replace("ы", "и")[:4]


class AIService:
    # Privacy terms are versioned data in knowledge/assistant_rules.json.
    PRIVACY_RESTRICTED_TERMS = tuple(load_assistant_rules().privacy_restricted_terms)
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

    @staticmethod
    def evidence_text(chunk) -> str:
        """Every reviewed language of a passage, so a question in any language can match."""
        languages: tuple[Language, ...] = ("en", "ru", "kk")
        texts = [source_text(chunk, language) for language in languages]
        return " ".join(f"{t['section_title']} {t['content']}" for t in texts if t)

    @staticmethod
    def relevance_model():
        """The trained JSON ranker when AI_RETRIEVAL_MODE=ml; None keeps lexical ranking."""
        if settings.AI_RETRIEVAL_MODE != "ml":
            return None
        try:
            return load_relevance_model(Path(settings.AI_RETRIEVAL_MODEL_PATH))
        except (OSError, ValueError) as exc:
            logging.getLogger("janamen").warning(
                "Retrieval model unavailable; using lexical retrieval (%s)", type(exc).__name__
            )
            return None

    @classmethod
    def rank_chunks(cls, db: Session, question: str, user_role: UserRole):
        """[(chunk, coverage, similarity)] for every passage readable in the current language.

        coverage   — share of meaningful question words found in the passage (strict gate);
        similarity — TF-IDF char n-gram cosine (ML ranking, tolerant to inflection).
        """
        chunks = [c for c in cls.accessible_chunks(db, user_role) if source_text(c) is not None]
        if not chunks:
            return []
        evidence = [f"{cls.evidence_text(c)} {c.tags or ''}" for c in chunks]
        similarity = ml_retrieval.rank(question, evidence)
        tokens = cls._tokenize(question)
        ranked = [
            (chunk, len(tokens & cls._tokenize(text)) / len(tokens) if tokens else 0.0, sim)
            for chunk, text, sim in zip(chunks, evidence, similarity)
        ]
        return sorted(ranked, key=lambda r: (-r[1], -r[2], r[0].id))

    @classmethod
    def strict_matches(cls, question: str, ranked) -> list:
        """Passages allowed for an extractive answer: the coverage gate always applies;
        the trained model (if enabled) can only re-order and further reject them."""
        gated = [c for c, cov, _sim in ranked if cov >= settings.AI_CONFIDENCE_THRESHOLD]
        model = cls.relevance_model()
        if model is None:
            return gated[:2]
        scored = []
        for chunk in gated:
            text = source_text(chunk)
            if text is None:
                continue
            score = model.score(
                relevance_features(
                    question,
                    text["section_title"],
                    f"{text['content']} {chunk.tags or ''}",
                    cls._tokenize,
                )
            )
            if score >= model.threshold:
                scored.append((score, chunk))
        return [c for _s, c in sorted(scored, key=lambda item: (-item[0], item[1].id))][:2]

    @classmethod
    def retrieve_relevant_chunks(cls, db: Session, question: str, user_role: UserRole):
        """Strict extractive matches with their coverage score (kept for callers and tests)."""
        ranked = cls.rank_chunks(db, question, user_role)
        coverage = {c.id: cov for c, cov, _sim in ranked}
        return [(c, coverage[c.id]) for c in cls.strict_matches(question, ranked)]

    @classmethod
    def is_private_question(cls, db: Session, user: User, question: str) -> bool:
        if is_private_text(question):
            return True
        rules = load_assistant_rules()
        text = question.lower()
        if not any(term in text for term in rules.privacy_sensitive_terms):
            return False
        # A sensitive word next to another employee's name ("зарплата Тимура").
        words = {_name_key(w) for w in re.findall(r"\w+", text) if len(w) >= 4}
        names = db.query(User.full_name).filter(User.id != user.id)
        return any(
            _name_key(part) in words for (name,) in names for part in name.split() if len(part) >= 4
        )

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.casefold().split())

    @classmethod
    def verify_llm_answer(cls, result, passages: list[dict]):
        """Accept a model answer only if it is fully backed by the passages it cites."""
        by_id = {p["id"]: p for p in passages}
        if not isinstance(result, dict) or result.get("answerable") is not True:
            return None
        answer, ids, quotes = result.get("answer"), result.get("source_ids"), result.get("quotes")
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 2000:
            return None
        if (
            not isinstance(ids, list)
            or not 1 <= len(ids) <= 3
            or not all(isinstance(i, str) and i in by_id for i in ids)
            or len(set(ids)) != len(ids)
        ):
            return None
        if not isinstance(quotes, list) or not 1 <= len(quotes) <= 5:
            return None
        cited = [by_id[i] for i in ids]
        covered = set()
        for quote in quotes:
            if not isinstance(quote, str) or not 12 <= len(quote.strip()) <= 2000:
                return None
            matches = {p["id"] for p in cited if quote in p["text"]}
            if not matches:
                return None
            covered.update(matches)
        # Quote existence does not prove a paraphrase. Display only exact selected text
        # from the current-language sources, with whitespace separators allowed.
        if set(ids) != covered or " ".join(answer.split()) != " ".join(" ".join(quotes).split()):
            return None
        return "\n\n".join(quotes), [p["chunk"] for p in cited]

    @classmethod
    def answer_with_llm(cls, question: str, ranked):
        """Returns ((answer, chunks), status); status is accepted/rejected/unavailable/skipped."""
        allowed_ids = {c.id for c in cls.strict_matches(question, ranked)}
        candidates = [
            chunk
            for chunk, coverage, sim in sorted(ranked, key=lambda r: (-r[2], r[0].id))
            if chunk.id in allowed_ids
        ][:3]
        if not candidates:
            return None, "skipped"
        passages = []
        for index, chunk in enumerate(candidates, start=1):
            text = source_text(chunk)
            if text is None:
                continue
            passages.append(
                {
                    "id": f"S{index}",
                    "title": f"{text['document_title']} — {text['section_title']}",
                    "text": text["content"],
                    "evidence": text["content"],
                    "chunk": chunk,
                }
            )
        result = gemini.generate_grounded_answer(question, passages, current_language.get())
        if result is None:
            return None, "unavailable"
        verified = cls.verify_llm_answer(result, passages)
        return (verified, "accepted") if verified else (None, "rejected")

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
        similarity: dict[int, float] = {}
        engine, llm_status = "extractive", "off"
        if cls.is_private_question(db, user, question):
            # Checked first, so private questions never reach retrieval or the model.
            answer_status = "unauthorized"
            answer = translate(
                "AI Jana protects employee privacy. Individual salaries, disciplinary and private employee "
                "records are not available through knowledge queries. Check your own profile or contact HR."
            )
        else:
            ranked = cls.rank_chunks(db, question, user.role)
            similarity = {chunk.id: sim for chunk, _cov, sim in ranked}
            chunks = cls.strict_matches(question, ranked)
            llm_answer = None
            if gemini.enabled():
                verified, llm_status = cls.answer_with_llm(question, ranked)
                if verified:
                    llm_answer, chunks = verified
                    engine = f"gemini:{settings.GEMINI_MODEL}"
            views = [(chunk, text) for chunk in chunks if (text := source_text(chunk)) is not None]
            answer_status = "grounded" if views else "fallback"
            answer = (
                translate(
                    "I couldn't find a reliable answer to this question in the approved knowledge base."
                )
                + " "
                + guidance
            )
            synthetic = translate("Synthetic example; not official HR policy.")
            if llm_answer:
                disclaimer = f"{synthetic} " if any(c.document.is_synthetic for c in chunks) else ""
                answer = f"{disclaimer}{llm_answer}"
            elif views:
                answer = "\n\n".join(
                    f"{synthetic + ' ' if c.document.is_synthetic else ''}"
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
                relevance=similarity.get(c.id),
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
                "engine": engine,
                "llm": llm_status,
                "source_ids": [c.id for c, _text in views],
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
            engine=engine,
            processing_time_ms=round((time.monotonic() - started) * 1000, 2),
        )


ai_service = AIService()
