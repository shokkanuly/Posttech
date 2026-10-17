"""Versioned assistant behavior; HR source approval remains a server-side check."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1] / "knowledge"


class AnswerRule(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,60}$")
    ru: str = Field(min_length=1, max_length=2000)
    kk: str = Field(min_length=1, max_length=2000)


class SourceRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: Literal[True]
    active: Literal[True]
    role_filtered: Literal[True]
    exact_quotes: Literal[True]
    revision_and_language_citations: Literal[True]
    employee_records_excluded: Literal[True]


class AssistantRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    source_requirements: SourceRequirements
    rules: list[AnswerRule] = Field(min_length=1, max_length=50)
    # Always private, whoever is asked about.
    privacy_restricted_terms: list[str] = Field(min_length=1, max_length=100)
    # Private only together with a pointer to another person: "аванс из зарплаты" is a
    # policy question, "зарплата у Тимура" / "оклад коллеги" is not.
    privacy_sensitive_terms: list[str] = Field(default_factory=list, max_length=100)
    privacy_other_person_markers: list[str] = Field(default_factory=list, max_length=100)


@lru_cache(maxsize=1)
def load_assistant_rules() -> AssistantRules:
    return AssistantRules.model_validate_json(
        (KNOWLEDGE_ROOT / "assistant_rules.json").read_text(encoding="utf-8")
    )


def is_private_text(question: str) -> bool:
    """Rule-file privacy check shared by the API and offline ML evaluation."""
    rules = load_assistant_rules()
    text = f" {question.lower()} "
    if any(term in text for term in rules.privacy_restricted_terms):
        return True
    return any(term in text for term in rules.privacy_sensitive_terms) and any(
        marker in text for marker in rules.privacy_other_person_markers
    )
