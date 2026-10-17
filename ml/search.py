"""Search only the offline synthetic file corpus. This CLI grants no application access."""

import argparse
import json
from pathlib import Path

from app.retrieval_ranker import load_relevance_model
from ml.data import ROOT, RetrievalQuery, load_corpus
from ml.retrieval import predict


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка поиска по вымышленным учебным файлам")
    parser.add_argument("--question", required=True)
    parser.add_argument("--language", choices=["ru", "kk"], default="ru")
    parser.add_argument("--role", choices=["employee", "manager", "hr_admin"], default="employee")
    parser.add_argument("--model", type=Path, default=ROOT / "ml/artifacts/relevance.json")
    args = parser.parse_args()
    query = RetrievalQuery(question=args.question, language=args.language, role=args.role)
    result = predict(query, load_corpus(), load_relevance_model(args.model))
    print(
        json.dumps(
            {
                "synthetic_demo": True,
                "status": result["status"],
                "sources": [
                    {
                        "demo_source_id": source["source_id"],
                        "section_title": source["title"],
                        "content": source["content"],
                        "relevance_score": round(score, 4),
                    }
                    for source, score in result["sources"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
