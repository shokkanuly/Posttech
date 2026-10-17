"""Validated synthetic retrieval examples with translation groups kept in one split."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.knowledge_files import read_bundle

ROOT = Path(__file__).resolve().parents[1]


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    language: Literal["ru", "kk"]
    role: Literal["employee", "manager", "hr_admin"]
    question: str = Field(min_length=1, max_length=2000)


class QueryExample(RetrievalQuery):
    id: str = Field(min_length=1, max_length=100)
    group_id: str = Field(min_length=1, max_length=100)
    expected_status: Literal["grounded", "fallback", "unauthorized"]
    relevant_source_ids: list[str] = Field(max_length=10)
    synthetic: Literal[True]

    @model_validator(mode="after")
    def consistent_label(self):
        if bool(self.relevant_source_ids) != (self.expected_status == "grounded"):
            raise ValueError("Only grounded examples must reference relevant sources")
        return self


def load_corpus(directory: Path = ROOT / "knowledge/documents") -> list[dict]:
    sources = []
    seen = set()
    for path in sorted(directory.glob("*.json")):
        bundle = read_bundle(path)
        if bundle.kind != "document" or not bundle.document.is_synthetic:
            raise ValueError("The bundled offline corpus must contain only synthetic documents")
        for section in bundle.sections:
            for language in [bundle.document.language, *bundle.document.translations]:
                identity = (bundle.bundle_id + ":" + section.key, language)
                if identity in seen:
                    raise ValueError("Duplicate source ID and language in corpus")
                seen.add(identity)
                translated = section.translations.get(language)
                sources.append(
                    {
                        "source_id": identity[0],
                        "language": language,
                        "title": translated.section_title if translated else section.section_title,
                        "content": translated.content if translated else section.content,
                        "tags": section.tags or "",
                        "access_level": section.access_level,
                    }
                )
    if not sources:
        raise ValueError("Corpus is empty")
    return sources


def load_examples(path: Path) -> list[QueryExample]:
    if path.stat().st_size > 5_242_880:
        raise ValueError("Dataset must not exceed 5 MiB")
    return [
        QueryExample.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def validate_splits(directory: Path, corpus: list[dict]) -> dict[str, list[QueryExample]]:
    splits = {
        name: load_examples(directory / (name + ".jsonl"))
        for name in ("train", "validation", "test")
    }
    groups: dict[str, str] = {}
    questions: dict[str, str] = {}
    ids: set[str] = set()
    for split, examples in splits.items():
        if not examples:
            raise ValueError("Dataset split must not be empty")
        for example in examples:
            normalized = " ".join(example.question.casefold().split())
            if example.id in ids:
                raise ValueError("Duplicate example ID")
            if example.group_id in groups and groups[example.group_id] != split:
                raise ValueError("Translation/paraphrase group leaks between dataset splits")
            if normalized in questions:
                raise ValueError("Duplicate question across the dataset")
            groups[example.group_id], questions[normalized] = split, split
            ids.add(example.id)
            permitted = {
                source["source_id"]
                for source in corpus
                if source["language"] == example.language
                and (source["access_level"] in ("all", example.role) or example.role == "hr_admin")
            }
            if not set(example.relevant_source_ids) <= permitted:
                raise ValueError("Label references an absent, untranslated or unauthorized source")
    return splits


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
