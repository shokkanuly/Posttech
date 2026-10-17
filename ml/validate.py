import json

from app.ai_rules import load_assistant_rules
from app.knowledge_files import read_bundle
from ml.data import ROOT, load_corpus, validate_splits


def main() -> None:
    rules = load_assistant_rules()
    corpus = load_corpus()
    splits = validate_splits(ROOT / "ml/data", corpus)
    for path in (ROOT / "knowledge/templates").glob("*.json"):
        read_bundle(path)
    print(
        json.dumps(
            {
                "valid": True,
                "assistant_rules": len(rules.rules),
                "source_passages": len(corpus),
                "split_sizes": {name: len(rows) for name, rows in splits.items()},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
