"""Offline evaluation shares features, tokenization and safety coverage with the API."""

from app.ai_rules import is_private_text
from app.retrieval_ranker import RelevanceModel, relevance_features
from app.services.ai_service import AIService
from ml.data import QueryExample, RetrievalQuery


def predict(example: RetrievalQuery, corpus: list[dict], model: RelevanceModel) -> dict:
    if is_private_text(example.question):
        return {"status": "unauthorized", "sources": []}
    ranked = []
    for source in corpus:
        if source["language"] != example.language:
            continue
        if source["access_level"] not in ("all", example.role) and example.role != "hr_admin":
            continue
        features = relevance_features(
            example.question,
            source["title"],
            source["content"] + " " + source["tags"],
            AIService._tokenize,
        )
        # A learned score can reorder evidence; it cannot remove the explicit coverage gate.
        if features[0] < 0.8:
            continue
        score = model.score(features)
        if score >= model.threshold:
            ranked.append((source, score))
    ranked.sort(key=lambda item: (-item[1], item[0]["source_id"]))
    return {"status": "grounded" if ranked else "fallback", "sources": ranked[:2]}


def evaluate(examples: list[QueryExample], corpus: list[dict], model: RelevanceModel) -> dict:
    totals = {
        "examples": len(examples),
        "status_correct": 0,
        "grounded": 0,
        "top1_correct": 0,
        "accepted": 0,
        "accepted_correct": 0,
        "fallback": 0,
        "fallback_correct": 0,
        "private": 0,
        "private_correct": 0,
    }
    errors = []
    for example in examples:
        prediction = predict(example, corpus, model)
        totals["status_correct"] += prediction["status"] == example.expected_status
        correct = (
            bool(prediction["sources"])
            and prediction["sources"][0][0]["source_id"] in example.relevant_source_ids
        )
        totals["accepted"] += bool(prediction["sources"])
        totals["accepted_correct"] += correct
        if example.expected_status == "grounded":
            totals["grounded"] += 1
            totals["top1_correct"] += correct
        elif example.expected_status == "fallback":
            totals["fallback"] += 1
            totals["fallback_correct"] += prediction["status"] == "fallback"
        else:
            totals["private"] += 1
            totals["private_correct"] += prediction["status"] == "unauthorized"
        if prediction["status"] != example.expected_status or (
            prediction["status"] == "grounded" and not correct
        ):
            errors.append(
                {
                    "id": example.id,
                    "expected": example.expected_status,
                    "actual": prediction["status"],
                    "top_source": prediction["sources"][0][0]["source_id"]
                    if prediction["sources"]
                    else None,
                }
            )

    def ratio(a, b):
        return round(totals[a] / totals[b], 4) if totals[b] else None

    return {
        "counts": totals,
        "status_accuracy": ratio("status_correct", "examples"),
        "grounded_top1_recall": ratio("top1_correct", "grounded"),
        "accepted_source_precision": ratio("accepted_correct", "accepted"),
        "fallback_accuracy": ratio("fallback_correct", "fallback"),
        "privacy_refusal_rate": ratio("private_correct", "private"),
        "errors": errors,
    }
