"""Locale negotiation and presentation text; wire enums and user input stay intact."""

import json
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from fastapi.routing import APIRoute
from starlette.requests import Request

Language = Literal["en", "ru", "kk"]
current_language: ContextVar[Language] = ContextVar("language", default="en")
CATALOG = json.loads(
    (Path(__file__).resolve().parents[1] / "static/locales/catalog.json").read_text()
)
PRESENTATION_FIELDS = {
    "full_name",
    "user_name",
    "manager_name",
    "reviewer_name",
    "actor_name",
    "position",
    "department",
    "company",
    "location",
    "greeting",
    "title",
    "description",
    "category",
    "content_markdown",
    "quiz_question",
    "quiz_options",
    "explanation",
    "message",
    "notes",
    "endpoint_template",
    "time_ago",
    "reason",
    "comment",
    "review_comment",
    "escalation_guidance",
}


def language_for(request: Request) -> Language:
    preferences = []
    for index, entry in enumerate(request.headers.get("accept-language", "en")[:1000].split(",")):
        tag, *parameters = entry.strip().lower().split(";")
        language = {"ru": "ru", "kk": "kk", "kz": "kk", "en": "en"}.get(tag.split("-")[0])
        quality = 1.0
        try:
            for parameter in parameters:
                if parameter.strip().startswith("q="):
                    quality = float(parameter.strip()[2:])
        except ValueError:
            continue
        if language and 0 < quality <= 1:
            preferences.append((quality, -index, language))
    return max(preferences)[2] if preferences else "en"  # type: ignore[return-value]


def translate(value: str, language: Language | None = None, depth: int = 0) -> str:
    language = language or current_language.get()
    if language == "en" or depth > 5:
        return value
    stripped = " ".join(value.split())
    message = CATALOG["messages"].get(stripped)
    if message:
        return message[language]
    for rule in CATALOG["rules"]:
        match = re.fullmatch(rule["pattern"], stripped)
        if match:
            return rule[language].format(
                *[translate(group or "", language, depth + 1) for group in match.groups()]
            )
    if " · " in stripped:
        return " · ".join(translate(part, language, depth + 1) for part in stripped.split(" · "))
    return value


def localize_payload(value, language: Language, field: str | None = None):
    if isinstance(value, dict):
        return {key: localize_payload(item, language, key) for key, item in value.items()}
    if isinstance(value, list):
        return [localize_payload(item, language, field) for item in value]
    if isinstance(value, str) and (field in PRESENTATION_FIELDS or field is None):
        return translate(value, language)
    return value


class LocalizedRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handle(request: Request):
            language = language_for(request)
            token = current_language.set(language)
            try:
                response = await original(request)
                content_language = language
                if response.headers.get("content-type", "").startswith("application/json"):
                    raw = json.loads(response.body)
                    if "/ai/chat" in request.url.path and isinstance(raw, dict):
                        content_language = raw.get("language", language)
                    elif language != "en":
                        payload = localize_payload(raw, language)
                        if "/ai/sources/" in request.url.path and isinstance(payload, dict):
                            content_language = payload.get("language", language)
                        response.body = json.dumps(
                            payload, ensure_ascii=False, separators=(",", ":")
                        ).encode()
                        response.headers["Content-Length"] = str(len(response.body))
                response.headers["Content-Language"] = content_language
                response.headers["Vary"] = "Accept-Language"
                return response
            finally:
                current_language.reset(token)

        return handle


def document_text(doc, language: Language | None = None) -> dict:
    language = language or current_language.get()
    original = {"title": doc.title, "category": doc.category, "description": doc.description}
    return (
        original if language == doc.language else (doc.translations or {}).get(language, original)
    )


def source_text(chunk, language: Language | None = None) -> dict | None:
    language = language or current_language.get()
    doc = chunk.document
    section: dict | None
    if language == doc.language:
        section = {"section_title": chunk.section_title, "content": chunk.content}
    else:
        section = (chunk.translations or {}).get(language)
        if not section or language not in (doc.translations or {}):
            return None
    return {
        **section,
        "document_title": document_text(doc, language)["title"],
        "language": language,
    }
