"""Portable linear relevance model. Artifacts contain JSON numbers, never executable pickle."""

import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Tokenizer = Callable[[str], set[str]]
FEATURE_NAMES = ("query_coverage", "token_jaccard", "char_trigram_cosine", "title_coverage")


def relevance_features(question: str, title: str, content: str, tokenize: Tokenizer) -> list[float]:
    query = tokenize(question)
    title_tokens = tokenize(title)
    passage = tokenize(title + " " + content)
    if not query:
        return [0.0] * len(FEATURE_NAMES)

    def trigrams(tokens: set[str]) -> Counter:
        return Counter(part[i : i + 3] for part in tokens for i in range(max(0, len(part) - 2)))

    a, b = trigrams(query), trigrams(passage)
    norm = math.sqrt(sum(v * v for v in a.values()) * sum(v * v for v in b.values()))
    cosine = sum(value * b[key] for key, value in a.items()) / norm if norm else 0.0
    return [
        len(query & passage) / len(query),
        len(query & passage) / len(query | passage),
        cosine,
        len(query & title_tokens) / len(query),
    ]


class RelevanceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1]
    feature_names: tuple[str, ...]
    coefficients: list[float] = Field(min_length=4, max_length=4)
    intercept: float = Field(ge=-1000, le=1000)
    threshold: float = Field(ge=0.5, le=0.99)
    training_manifest: dict[str, str]

    @field_validator("feature_names")
    @classmethod
    def supported_features(cls, value):
        if value != FEATURE_NAMES:
            raise ValueError("Unsupported retrieval features; retrain with the current code")
        return value

    @field_validator("coefficients")
    @classmethod
    def bounded_weights(cls, value):
        if any(abs(number) > 1000 for number in value):
            raise ValueError("Retrieval weights exceed supported bounds")
        return value

    def score(self, features: list[float]) -> float:
        if len(features) != len(self.coefficients):
            raise ValueError("Unexpected feature count")
        value = self.intercept + sum(a * b for a, b in zip(self.coefficients, features))
        return 1 / (1 + math.exp(-max(-700.0, min(700.0, value))))


@lru_cache(maxsize=4)
def _read_model(path: str, mtime_ns: int, size: int) -> RelevanceModel:
    return RelevanceModel.model_validate_json(Path(path).read_text(encoding="utf-8"))


def load_relevance_model(path: Path) -> RelevanceModel:
    stat = path.stat()
    if stat.st_size > 262144:
        raise ValueError("Retrieval model exceeds 256 KiB")
    return _read_model(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
