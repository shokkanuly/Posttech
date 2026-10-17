"""Train a small relevance ranker locally; export coefficients in a safe JSON format."""

import argparse
import hashlib
from pathlib import Path

from app.retrieval_ranker import FEATURE_NAMES, RelevanceModel, relevance_features
from app.services.ai_service import AIService
from ml.data import ROOT, load_corpus, validate_splits, write_json
from ml.retrieval import evaluate


def train(data_dir: Path, output: Path, report: Path) -> RelevanceModel:
    try:
        import sklearn
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise RuntimeError(
            "Install optional training dependencies: pip install -r requirements-ml.txt"
        ) from exc
    corpus = load_corpus()
    splits = validate_splits(data_dir, corpus)
    features, labels = [], []
    for example in splits["train"]:
        for source in corpus:
            if source["language"] != example.language:
                continue
            if source["access_level"] not in ("all", example.role) and example.role != "hr_admin":
                continue
            features.append(
                relevance_features(
                    example.question,
                    source["title"],
                    source["content"] + " " + source["tags"],
                    AIService._tokenize,
                )
            )
            labels.append(int(source["source_id"] in example.relevant_source_ids))
    if set(labels) != {0, 1}:
        raise ValueError("Training requires relevant and irrelevant query/source pairs")
    classifier = LogisticRegression(class_weight="balanced", random_state=17, max_iter=1000)
    classifier.fit(features, labels)
    manifest = {
        split + "_sha256": hashlib.sha256((data_dir / (split + ".jsonl")).read_bytes()).hexdigest()
        for split in splits
    }
    manifest["scikit_learn_version"] = sklearn.__version__
    manifest["corpus_sha256"] = hashlib.sha256(repr(corpus).encode()).hexdigest()
    model = RelevanceModel(
        schema_version=1,
        feature_names=FEATURE_NAMES,
        coefficients=classifier.coef_[0].tolist(),
        intercept=float(classifier.intercept_[0]),
        threshold=0.5,
        training_manifest=manifest,
    )
    # Select on validation only. The held-out test split never chooses model parameters.
    candidates = []
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        candidate = model.model_copy(update={"threshold": threshold})
        metrics = evaluate(splits["validation"], corpus, candidate)
        counts = metrics["counts"]
        utility = counts["accepted_correct"] - 3 * (counts["accepted"] - counts["accepted_correct"])
        candidates.append((utility, counts["status_correct"], threshold))
    model.threshold = max(candidates)[2]
    # Check that portable inference matches the fitted estimator before saving it.
    for row, expected in zip(features, classifier.predict_proba(features)[:, 1]):
        if abs(model.score(row) - float(expected)) > 1e-10:
            raise RuntimeError("Portable model prediction differs from training estimator")
    write_json(output, model.model_dump())
    write_json(
        report,
        {
            "model": "LogisticRegression over four query/source relevance features",
            "synthetic_only": True,
            "minimum_query_coverage": 0.8,
            "threshold": model.threshold,
            "split_sizes": {name: len(rows) for name, rows in splits.items()},
            "training_pairs": len(labels),
            "manifest": manifest,
            "validation": evaluate(splits["validation"], corpus, model),
            "test": evaluate(splits["test"], corpus, model),
            "test_by_language": {
                language: evaluate(
                    [r for r in splits["test"] if r.language == language], corpus, model
                )
                for language in ("ru", "kk")
            },
            "limitations": [
                "Small synthetic demonstration dataset; not a production quality estimate.",
                "Lexical coverage remains mandatory; this is not semantic embedding search.",
                "No real company policy or personal HR data is used.",
            ],
        },
    )
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальное обучение поиска кадровых документов")
    parser.add_argument("--data", type=Path, default=ROOT / "ml/data")
    parser.add_argument("--output", type=Path, default=ROOT / "ml/artifacts/relevance.json")
    parser.add_argument("--report", type=Path, default=ROOT / "ml/reports/baseline.json")
    args = parser.parse_args()
    model = train(args.data, args.output, args.report)
    print(f"Модель сохранена: {args.output}; порог: {model.threshold}; отчёт: {args.report}")


if __name__ == "__main__":
    main()
