import argparse
import json
from pathlib import Path

from app.retrieval_ranker import load_relevance_model
from ml.data import ROOT, load_corpus, load_examples
from ml.retrieval import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка модели поиска на отдельном наборе")
    parser.add_argument("--model", type=Path, default=ROOT / "ml/artifacts/relevance.json")
    parser.add_argument("--data", type=Path, default=ROOT / "ml/data/test.jsonl")
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate(load_examples(args.data), load_corpus(), load_relevance_model(args.model)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
