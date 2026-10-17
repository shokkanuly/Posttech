"""TF-IDF ranking over character n-grams (the classic char_wb vector space model).

Character 3–5-grams inside word boundaries make inflected Russian/Kazakh forms
(отпуск / отпуска / отпуском, демалыс / демалысқа) share most features without a
stemmer, and the IDF weight pushes rare, topical n-grams above common ones.
Pure Python: the approved knowledge base is small and is re-indexed per query,
so an edited or newly approved source is ranked immediately.
"""

import math
import re
from collections import Counter

_WORD = re.compile(r"\w+", re.UNICODE)


def _features(text: str) -> Counter:
    grams: Counter = Counter()
    for word in _WORD.findall(text.lower()):
        padded = f" {word} "
        for n in (3, 4, 5):
            grams.update(padded[i : i + n] for i in range(len(padded) - n + 1))
    return grams


def rank(question: str, documents: list[str]) -> list[float]:
    """Cosine similarity (0..1) between the question and each document."""
    if not documents:
        return []
    doc_features = [_features(d) for d in documents]
    df: Counter = Counter()
    for features in doc_features:
        df.update(features.keys())
    total = len(documents)
    idf = {gram: math.log((1 + total) / (1 + count)) + 1 for gram, count in df.items()}

    def vector(features: Counter) -> dict[str, float]:
        weighted = {g: (1 + math.log(c)) * idf.get(g, 0.0) for g, c in features.items()}
        norm = math.sqrt(sum(w * w for w in weighted.values())) or 1.0
        return {g: w / norm for g, w in weighted.items()}

    query = vector(_features(question))
    return [
        round(sum(w * query.get(g, 0.0) for g, w in vector(f).items()), 4) for f in doc_features
    ]


if __name__ == "__main__":
    docs = [
        "Vacation request workflow. Заявка на отпуск: укажите даты отпуска.",
        "Advance payment policy. Аванс до 50% оклада.",
        "Working hours 09:00 to 18:00. Рабочее время.",
    ]
    scores = rank("как оформить отпуском", docs)
    assert scores[0] == max(scores) and scores[0] > 0, scores
    assert rank("аванса", docs).index(max(rank("аванса", docs))) == 1
    assert rank("", docs) == [0.0, 0.0, 0.0] and rank("x", []) == []
    print("ok", scores)
