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


# Kazakh and soft letters folded so "Dana", "Даны" and "Дананың" share one spelling.
_FOLD = str.maketrans("йыіёәөұүғқңһ", "иииеаоуугкнх", "ьъ")
# Russian/Kazakh case endings after folding: Тимура, Даной, Тимурдың, Дананың, Данаға.
_NAME_ENDINGS = (
    *("", "а", "я", "и", "е", "у", "ю", "ои", "еи", "ою", "ом", "ем", "им"),
    *("нин", "дин", "тин", "га", "ге", "ка", "ке", "на", "не", "ни", "ди", "ти", "н"),
    *("да", "де", "та", "те", "нда", "нде", "дан", "ден", "тан", "тен", "нан", "нен"),
    *("мен", "бен", "пен"),
)


def _fold(word: str) -> str:
    word = word.lower()
    for latin, cyrillic in _TRANSLIT:
        word = word.replace(latin, cyrillic)
    return word.translate(_FOLD)


def _is_name_form(word: str, names: set[str]) -> bool:
    """word (folded) is a case form of a name: Тимур+а, or Дан(а)+ы with the final vowel dropped."""
    for ending in _NAME_ENDINGS:
        if word.endswith(ending):
            base = word[: len(word) - len(ending)]
            if base in names or (ending and (base + "а" in names or base + "я" in names)):
                return True
    return False


KAZAKH_SPECIFIC_CHARS = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
KAZAKH_MARKER_WORDS = {
    "қалай",
    "калай",
    "қандай",
    "кандай",
    "қайда",
    "кайда",
    "қайдан",
    "кайдан",
    "демалыс",
    "демалысқа",
    "демалыска",
    "демалысы",
    "демалысым",
    "өтініш",
    "отиниш",
    "өтінішті",
    "отиништи",
    "өтініштер",
    "отиништер",
    "өтінішім",
    "авансқа",
    "аванска",
    "авансты",
    "авансы",
    "жұмыс",
    "жумыс",
    "жұмысы",
    "жумысы",
    "кестесі",
    "кестеси",
    "уақыты",
    "уакыты",
    "күн",
    "күндер",
    "кундер",
    "күндері",
    "кундери",
    "күндерім",
    "кундерим",
    "күнтізбелік",
    "оқу",
    "оку",
    "сабақ",
    "сабак",
    "өту",
    "оту",
    "өтуге",
    "отуге",
    "өткім",
    "отким",
    "өтемін",
    "отемин",
    "көмек",
    "комек",
    "қалдық",
    "калдык",
    "қалдығы",
    "калдыгы",
    "қалдығым",
    "қалдықтан",
    "болады",
    "бола",
    "болу",
    "болуы",
    "керек",
    "қажет",
    "кажет",
    "аламын",
    "алуға",
    "алуга",
    "беремін",
    "беремин",
    "беру",
    "беруге",
    "берсем",
    "істеймін",
    "истеймин",
    "істеу",
    "истеу",
    "қанша",
    "канша",
    "неше",
    "маған",
    "маган",
    "менің",
    "менин",
    "сенің",
    "сенин",
    "сіздің",
    "сиздин",
    "біздің",
    "биздин",
    "ауырып",
    "қалсам",
    "калсам",
    "қалса",
    "калса",
    "сырқат",
    "еңбекке",
    "жарамсыздық",
}

KAZAKH_SUFFIXES = (
    "тарымыз",
    "теріміз",
    "дарымыз",
    "деріміз",
    "ларымыз",
    "леріміз",
    "тардың",
    "тердің",
    "дардың",
    "дердің",
    "лардың",
    "лердің",
    "тардан",
    "терден",
    "дардан",
    "дерден",
    "лардан",
    "лерден",
    "тармен",
    "термен",
    "дармен",
    "дермен",
    "лармен",
    "лермен",
    "тары",
    "тері",
    "дары",
    "дері",
    "лары",
    "лері",
    "тарға",
    "терге",
    "дарға",
    "дерге",
    "ларға",
    "лерге",
    "тарды",
    "терді",
    "дарды",
    "дерді",
    "ларды",
    "лерді",
    "тарда",
    "терде",
    "дарда",
    "дерде",
    "ларда",
    "лерде",
    "ымыз",
    "іміз",
    "ыңыз",
    "іңіз",
    "сызда",
    "сізде",
    "тар",
    "тер",
    "дар",
    "дер",
    "лар",
    "лер",
    "дан",
    "ден",
    "тан",
    "тен",
    "нан",
    "нен",
    "мен",
    "бен",
    "пен",
    "дың",
    "дің",
    "тың",
    "тің",
    "ның",
    "нің",
    "ды",
    "ді",
    "ты",
    "ті",
    "ны",
    "ні",
    "да",
    "де",
    "та",
    "те",
    "нда",
    "нде",
    "ға",
    "ге",
    "қа",
    "ке",
    "на",
    "не",
    "ым",
    "ім",
    "ың",
    "ің",
    "сы",
    "сі",
)


def detect_query_language(text: str) -> Language | None:
    if any(char in KAZAKH_SPECIFIC_CHARS for char in text):
        return "kk"
    words = {w.lower() for w in re.findall(r"\w+", text)}
    if words & KAZAKH_MARKER_WORDS:
        return "kk"
    has_cyrillic = bool(re.search(r"[а-яА-ЯёЁ]", text))
    has_latin = bool(re.search(r"[a-zA-Z]", text))
    if has_cyrillic and not has_latin:
        return "ru"
    if has_latin and not has_cyrillic:
        return "en"
    return None


class AIService:
    # Privacy terms are versioned data in knowledge/assistant_rules.json.
    PRIVACY_RESTRICTED_TERMS = tuple(load_assistant_rules().privacy_restricted_terms)
    STOP_WORDS = set(
        (
            "what the for with from how does can are and this that policy rules about guide sample "
            "where find many get official jana post system please tell explain employees employee "
            "should must would could my your their its into do is has have not which when why "
            "что как для или это где правила инструкция туралы ереже "
            "подскажите какой какая какие как где посмотреть системе мой мои мне есть могу можно для нужно "
            "положено делать если когда мен хочу хотел хотела хотим желаю "
            "қалай қандай қайда қайдан кім не неге қашан "
            "көремін жүйеде келеді керек қажет болады бола болу болуы істеймін істеу "
            "қалсам қалса болсам болса "
            "маған менің сенің сіздің біздің оның олардың "
            "дейін үшін арқылы бойы бойынша бар жоқ еді екен "
            "отдел отдела отделом бөлім бөлімі бөліміне бөлімін"
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
                "отпуском",
                "отпусках",
                "демалыс",
                "демалысқа",
                "демалысы",
                "демалысым",
                "демалысын",
                "демалыстар",
                "демалысының",
                "демалыспен",
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
                "подача",
                "запросить",
                "запрос",
                "оформить",
                "оформление",
                "взять",
                "получить",
                "получение",
                "өтініш",
                "өтінішті",
                "өтініштер",
                "өтінішім",
                "өтінішке",
                "өтініштің",
                "беру",
                "беруге",
                "беремін",
                "берсем",
                "беріп",
                "беріледі",
                "сұрау",
                "сұрауға",
                "сұраймын",
                "алу",
                "алуға",
                "аламын",
                "алам",
                "алсам",
            ),
            "request",
        ),
        **dict.fromkeys(
            (
                "остаток",
                "остатка",
                "остатки",
                "баланс",
                "баланса",
                "қалдық",
                "қалдығы",
                "қалдығын",
                "қалдықтан",
                "қалдықты",
                "қалдығым",
            ),
            "balance",
        ),
        **dict.fromkeys(
            (
                "день",
                "дней",
                "дня",
                "дни",
                "күн",
                "күндер",
                "күндері",
                "күндерім",
                "күндерін",
                "күндерінің",
                "күнге",
                "күнтізбелік",
            ),
            "day",
        ),
        **dict.fromkeys(
            (
                "аванс",
                "аванса",
                "авансу",
                "авансом",
                "авансқа",
                "авансты",
                "авансы",
                "аванстың",
                "зарплата",
                "зарплаты",
                "зарплату",
                "жалақы",
                "айлық",
            ),
            "advance",
        ),
        **dict.fromkeys(
            (
                "график",
                "графика",
                "графике",
                "кесте",
                "кестесі",
                "кестеде",
                "кестесін",
                "уақыты",
                "уақыт",
                "сағат",
            ),
            "schedule",
        ),
        **dict.fromkeys(
            (
                "работа",
                "работы",
                "работе",
                "рабочее",
                "рабочий",
                "жұмыс",
                "жұмыстың",
                "жұмысы",
                "жұмысқа",
            ),
            "work",
        ),
        **dict.fromkeys(
            (
                "заболел",
                "заболела",
                "болезнь",
                "болею",
                "ауырып",
                "ауырған",
                "ауырғанда",
                "ауру",
                "сырқат",
                "ауырсам",
            ),
            "illness",
        ),
        **dict.fromkeys(
            (
                "кадровую",
                "кадровая",
                "кадровой",
                "кадр",
                "кадры",
                "службу",
                "служба",
                "қызметі",
                "hr",
            ),
            "hr",
        ),
        **dict.fromkeys(
            (
                "контакты",
                "связаться",
                "обратиться",
                "байланыс",
                "байланысу",
                "байланысуға",
                "хабарласу",
                "хабарласуға",
                "хабарласамын",
                "позвонить",
                "написать",
            ),
            "contact",
        ),
        **dict.fromkeys(
            (
                "курс",
                "курсы",
                "курса",
                "курсу",
                "курсе",
                "курстар",
                "курсты",
                "курстарды",
                "курстардан",
                "курстан",
                "обучение",
                "обучения",
                "академия",
                "академии",
                "академиясы",
                "academy",
                "courses",
                "course",
                "learning",
                "оқу",
                "оқуды",
                "оқыту",
                "сабақ",
                "сабақтар",
            ),
            "course",
        ),
        **dict.fromkeys(
            (
                "пройти",
                "прохождение",
                "проходить",
                "пройду",
                "записаться",
                "запись",
                "өту",
                "өтуге",
                "өтуі",
                "өткім",
                "өтеді",
                "өтемін",
                "тіркелу",
                "жазылу",
                "тапсыру",
                "бітіру",
                "аяқтау",
                "complete",
                "enroll",
                "pass",
            ),
            "pass_course",
        ),
        **dict.fromkeys(("сколько", "сколь", "қанша", "канша", "неше"), "how_many"),
    }
    # ponytail: RU/KK inflect heavily, so Cyrillic words match on a 5-letter prefix
    # (отпуском ~ отпуска). Avoid 'хабар' prefix matching 'хабарлап' (notify manager).
    base_aliases = {
        k[:5]: v for k, v in ALIASES.items() if not k.isascii() and not k.startswith("хабар")
    }
    base_aliases["хабарлас"] = "contact"
    base_aliases["хабарласу"] = "contact"
    base_aliases["хабарласуға"] = "contact"
    base_aliases["хабарласамын"] = "contact"
    ALIASES |= base_aliases
    STOP_WORDS |= {w[:5] for w in STOP_WORDS if not w.isascii()}

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        text = text.lower().replace("time off", "vacation").replace("carry over", "carryover")
        tokens = set()
        for t in re.findall(r"\w+", text):
            if t in cls.STOP_WORDS:
                continue
            if t in cls.ALIASES:
                tokens.add(cls.ALIASES[t])
                continue
            stem = t
            for sfx in KAZAKH_SUFFIXES:
                if len(t) - len(sfx) >= 3 and t.endswith(sfx):
                    cand = t[: -len(sfx)]
                    if cand in cls.ALIASES or cand in cls.STOP_WORDS:
                        stem = cand
                        break
            if stem in cls.STOP_WORDS:
                continue
            if stem in cls.ALIASES:
                tokens.add(cls.ALIASES[stem])
                continue
            prefix = stem if stem.isascii() or stem in cls.ALIASES else stem[:5]
            if len(stem) > 2 and prefix not in cls.STOP_WORDS:
                tokens.add(cls.ALIASES.get(prefix, prefix))
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
    def rank_chunks(
        cls, db: Session, question: str, user_role: UserRole, language: Language | None = None
    ):
        """[(chunk, coverage, similarity)] for every passage readable in the target language.

        coverage   — share of meaningful question words found in the passage (strict gate);
        similarity — TF-IDF char n-gram cosine (ML ranking, tolerant to inflection).
        """
        target_lang = language or current_language.get()
        chunks = [
            c
            for c in cls.accessible_chunks(db, user_role)
            if source_text(c, target_lang) is not None
        ]
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
    def strict_matches(cls, question: str, ranked, language: Language | None = None) -> list:
        """Passages allowed for an extractive answer: the coverage gate always applies;
        the trained model (if enabled) can only re-order and further reject them."""
        target_lang = language or current_language.get()
        gated = [c for c, cov, _sim in ranked if cov >= settings.AI_CONFIDENCE_THRESHOLD]
        model = cls.relevance_model()
        if model is None:
            return gated[:2]
        scored = []
        for chunk in gated:
            text = source_text(chunk, target_lang)
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
    def retrieve_relevant_chunks(
        cls, db: Session, question: str, user_role: UserRole, language: Language | None = None
    ):
        """Strict extractive matches with their coverage score (kept for callers and tests)."""
        target_lang = language or current_language.get()
        ranked = cls.rank_chunks(db, question, user_role, target_lang)
        coverage = {c.id: cov for c, cov, _sim in ranked}
        return [(c, coverage[c.id]) for c in cls.strict_matches(question, ranked, target_lang)]

    @classmethod
    def is_private_question(cls, db: Session, user: User, question: str) -> bool:
        if is_private_text(question):
            return True
        rules = load_assistant_rules()
        text = question.lower()
        topics = rules.privacy_sensitive_terms + rules.privacy_record_terms
        if not any(term in text for term in topics):
            return False
        # A salary or leave word next to another employee's name ("отпуск у Даны").
        # ponytail: first names only — demo accounts carry role words as surnames
        # ("Демо Сотрудник"); add surnames with a stop-list once real HR names are loaded.
        names = {
            key
            for (name,) in db.query(User.full_name).filter(User.id != user.id)
            for part in name.split()[:1]
            if len(key := _fold(part)) >= 4
        }
        return any(_is_name_form(_fold(word), names) for word in re.findall(r"\w+", text))

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
    def answer_with_llm(cls, question: str, ranked, language: Language | None = None):
        """Returns ((answer, chunks), status); status is accepted/rejected/unavailable/skipped."""
        target_lang = language or current_language.get()
        allowed_ids = {c.id for c in cls.strict_matches(question, ranked, target_lang)}
        candidates = [
            chunk
            for chunk, coverage, sim in sorted(ranked, key=lambda r: (-r[2], r[0].id))
            if chunk.id in allowed_ids
        ][:3]
        if not candidates:
            return None, "skipped"
        passages = []
        for index, chunk in enumerate(candidates, start=1):
            text = source_text(chunk, target_lang)
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
        result = gemini.generate_grounded_answer(question, passages, target_lang)
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

        detected_lang = detect_query_language(question)
        if detected_lang == "kk":
            effective_language: Language = "kk"
        elif current_language.get() == "kk":
            effective_language = "kk"
        elif detected_lang == "ru":
            effective_language = "ru"
        elif detected_lang == "en":
            effective_language = "en"
        else:
            effective_language = current_language.get()

        guidance = translate(
            f"Contact HR support at {settings.HR_SUPPORT_EMAIL} for confirmation.",
            language=effective_language,
        )
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
                "records are not available through knowledge queries. Check your own profile or contact HR.",
                language=effective_language,
            )
        else:
            ranked = cls.rank_chunks(db, question, user.role, language=effective_language)
            similarity = {chunk.id: sim for chunk, _cov, sim in ranked}
            chunks = cls.strict_matches(question, ranked, language=effective_language)
            llm_answer = None
            if gemini.enabled():
                verified, llm_status = cls.answer_with_llm(
                    question, ranked, language=effective_language
                )
                if verified:
                    llm_answer, chunks = verified
                    engine = f"gemini:{settings.GEMINI_MODEL}"
            views = [
                (chunk, text)
                for chunk in chunks
                if (text := source_text(chunk, effective_language)) is not None
            ]
            answer_status = "grounded" if views else "fallback"
            answer = (
                translate(
                    "I couldn't find a reliable answer to this question in the approved knowledge base.",
                    language=effective_language,
                )
                + " "
                + guidance
            )
            synthetic = translate(
                "Synthetic example; not official HR policy.", language=effective_language
            )
            source_label = translate("Source:", language=effective_language)
            if llm_answer:
                disclaimer = f"{synthetic} " if any(c.document.is_synthetic for c in chunks) else ""
                answer = f"{disclaimer}{llm_answer}"
            elif views:
                answer = "\n\n".join(
                    f"{synthetic + ' ' if c.document.is_synthetic else ''}"
                    f"{source_label} {text['document_title']} — {text['section_title']} (v{c.document.version})\n{text['content']}"
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
                language=effective_language,
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
                        "language": effective_language,
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
            language=effective_language,
        )


ai_service = AIService()
