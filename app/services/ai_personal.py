"""AI Jana answers about the asking employee's own records, never anyone else's.

Runs only after the privacy guard. Reads the current user's profile, requests and courses
and fills fixed templates, so every number and date is exact. Nothing here is sent to an
external model.
"""

import re
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import leave_calendar
from app.localization import Language, translate
from app.models.enums import RequestStatus, RequestType
from app.models.request import Request
from app.models.user import User
from app.services import request_service as requests_module
from app.services.academy_service import academy_service
from app.services.request_service import request_service

# Words that point at the asker ("у меня", "менің", Kazakh possessive forms, "my").
SELF = {
    *("я", "мой", "моя", "мои", "моё", "мое", "моего", "моей", "моих", "мне", "меня", "мной"),
    *("мою", "моему", "моим", "моими", "моём", "моем"),
    *("мен", "менің", "маған", "менде", "мені", "демалысым", "күндерім", "қалдығым"),
    *("өтінішім", "өтініштерім", "курстарым", "курсым", "басшым", "i", "my", "me", "mine"),
}
TOPICS = {
    "leave": ("отпуск", "демалыс", "vacation", "leave", "остат", "баланс", "қалдық", "калдык"),
    "requests": ("заяв", "өтініш", "отиниш", "request"),
    "courses": ("курс", "обучени", "оқу", "академ", "course", "training", "дедлайн"),
    "manager": ("руководител", "начальник", "басшы", "manager"),
}
HOLIDAY_WORDS = ("праздник", "мереке", "holiday")
# "Как оформить отпуск?" asks for the procedure; the knowledge base answers that alone.
HOW_TO = ("как ", "how do", "how to", "how can", "қалай", "калай")

TEXT = {
    "intro": {
        "ru": "По вашим данным в JanaМен:",
        "kk": "JanaМен-дегі деректеріңіз бойынша:",
        "en": "From your JanaМен records:",
    },
    "leave": {
        "ru": "Остаток отпуска: {balance} дн. На рассмотрении: {pending} дн. Доступно для новой заявки: {available} дн.",
        "kk": "Демалыс қалдығы: {balance} күн. Қаралуда: {pending} күн. Жаңа өтінішке қолжетімді: {available} күн.",
        "en": "Leave balance: {balance} days. Pending: {pending} days. Available for a new request: {available} days.",
    },
    "next_vacation": {
        "ru": "Ближайший отпуск: {period} ({code}, {status}).",
        "kk": "Жақын демалыс: {period} ({code}, {status}).",
        "en": "Next vacation: {period} ({code}, {status}).",
    },
    "requests": {"ru": "Последние заявки:", "kk": "Соңғы өтініштер:", "en": "Recent requests:"},
    "no_requests": {
        "ru": "Заявок пока нет.",
        "kk": "Әзірге өтініш жоқ.",
        "en": "No requests yet.",
    },
    "courses": {
        "ru": "Назначенные курсы:",
        "kk": "Тағайындалған курстар:",
        "en": "Assigned courses:",
    },
    "due": {"ru": "срок до {date}", "kk": "мерзімі {date} дейін", "en": "due {date}"},
    "no_courses": {
        "ru": "Назначенных курсов нет.",
        "kk": "Тағайындалған курс жоқ.",
        "en": "No assigned courses.",
    },
    "manager": {
        "ru": "Ваш руководитель: {name}.",
        "kk": "Сіздің басшыңыз: {name}.",
        "en": "Your manager: {name}.",
    },
    "no_manager": {
        "ru": "Руководитель не назначен; заявки рассматривает HR.",
        "kk": "Басшы тағайындалмаған; өтініштерді HR қарайды.",
        "en": "No manager is assigned; HR reviews your requests.",
    },
    "holidays": {
        "ru": "Ближайшие праздники (в отпуск не входят):",
        "kk": "Жақын мерекелер (демалысқа кірмейді):",
        "en": "Upcoming public holidays (not charged to leave):",
    },
}
MONTHS = {
    "ru": "января февраля марта апреля мая июня июля августа сентября октября ноября декабря",
    "kk": "қаңтар ақпан наурыз сәуір мамыр маусым шілде тамыз қыркүйек қазан қараша желтоқсан",
    "en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
}


def _date(day: date, lang: Language) -> str:
    month = MONTHS[lang].split()[day.month - 1]
    return f"{day.day} {month} {day.year}" + {"ru": " г.", "kk": " ж.", "en": ""}[lang]


def _num(value: float | Decimal) -> str:
    return f"{value:g}"


def _period(req: Request, lang: Language) -> str:
    if req.type == RequestType.PROFILE_UPDATE:
        return ", ".join(
            translate(field.replace("_", " ").capitalize(), lang)
            for field in req.profile_changes or {}
        )
    if req.type == RequestType.ADVANCE_PAYMENT:
        return f"{_num(req.amount or 0)} ₸ · {_date(req.start_date, lang)}"
    end = req.end_date or req.start_date
    start = _date(req.start_date, lang)
    return start if end == req.start_date else f"{start} — {_date(end, lang)}"


def topics(question: str) -> list[str]:
    text = f" {question.lower()} "
    words = set(re.findall(r"\w+", text))
    found = ["holidays"] if any(w in text for w in HOLIDAY_WORDS) else []
    if words & SELF and not any(marker in text for marker in HOW_TO):
        found += [name for name, stems in TOPICS.items() if any(s in text for s in stems)]
    return found


def personal_facts(db: Session, user: User, question: str, lang: Language) -> tuple[list[str], str]:
    """(topics answered, text) for the asker's own records; ([], "") when none apply."""
    asked = topics(question)
    lines: list[str] = []
    profile = user.profile
    if "leave" in asked and profile:
        summary = request_service.leave_summary(db, [user.id])[user.id]
        available = max(0.0, profile.leave_balance_days - summary["pending_days"])
        lines.append(
            TEXT["leave"][lang].format(
                balance=_num(profile.leave_balance_days),
                pending=_num(summary["pending_days"]),
                available=_num(available),
            )
        )
        upcoming = (
            db.query(Request)
            .filter(
                Request.user_id == user.id,
                Request.type == RequestType.VACATION,
                Request.status.in_([RequestStatus.PENDING, RequestStatus.APPROVED]),
                Request.start_date >= requests_module.request_today(),
            )
            .order_by(Request.start_date)
            .first()
        )
        if upcoming:
            lines.append(
                TEXT["next_vacation"][lang].format(
                    period=_period(upcoming, lang),
                    code=upcoming.request_code,
                    status=translate(upcoming.status.value, lang),
                )
            )
    if "requests" in asked:
        recent = (
            db.query(Request)
            .filter(Request.user_id == user.id)
            .order_by(Request.created_at.desc(), Request.id.desc())
            .limit(5)
            .all()
        )
        lines.append(TEXT["requests" if recent else "no_requests"][lang])
        lines += [
            f"• {r.request_code} · {translate(r.type.value, lang)} · {_period(r, lang)} · "
            f"{translate(r.status.value, lang)}"
            for r in recent
        ]
    if "courses" in asked:
        courses = [c for c in academy_service.get_user_courses(db, user) if c.assigned]
        lines.append(TEXT["courses" if courses else "no_courses"][lang])
        for c in courses:
            due = (
                f", {TEXT['due'][lang].format(date=_date(c.due_date, lang))}" if c.due_date else ""
            )
            lines.append(f"• {translate(c.title, lang)} — {round(c.progress_percent)}%{due}")
    if "manager" in asked and profile:
        manager = profile.manager
        lines.append(
            TEXT["manager"][lang].format(name=translate(manager.full_name, lang))
            if manager
            else TEXT["no_manager"][lang]
        )
    if "holidays" in asked:
        today = requests_module.request_today()
        upcoming_days = [
            d
            for d in leave_calendar.breakdown(today, date(today.year + 1, 12, 31))
            if d["kind"] == "holiday"
        ][:4]
        lines.append(TEXT["holidays"][lang])
        lines += [
            f"• {_date(d['day'], lang)} — {translate(d['holiday'], lang)}" for d in upcoming_days
        ]
    if not lines:
        return [], ""
    intro = [TEXT["intro"][lang]] if set(asked) - {"holidays"} else []
    return asked, "\n".join([*intro, *lines])
