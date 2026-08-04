import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from src.internal.db.vector import ingest_chroma, query_chroma
from src.utils.logger import get_logger

logger = get_logger(__name__)


def ingest(input_path: str) -> None:
    logger.info("starting Chroma ingest", extra={"input": input_path})
    count = ingest_chroma(input_path)
    from src.internal.settings import settings
    logger.info("Chroma ingest complete", extra={"collection": settings.chroma_collection, "count": count})
    print(f"Ingested {count} records into Chroma collection '{settings.chroma_collection}'")


def query(query_text: str, n_results: int = 5) -> None:
    logger.info("querying Chroma", extra={"query": query_text[:100], "n_results": n_results})
    results = query_chroma(query_text, n_results)
    logger.info("Chroma query returned", extra={"count": len(results)})
    for i, r in enumerate(results):
        meta = r["metadata"]
        print(f"\n--- Result {i + 1} (distance={r['distance']:.4f}) ---")
        print(f"Category: {meta.get('category', '?')}  |  Ref: {meta.get('ref', '?')}  |  Tags: {meta.get('tags', '')}")
        doc = r["document"]
        print(doc[:500])
        if len(doc) > 500:
            print("...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChromaDB vector pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest embeddings.jsonl into Chroma")
    ingest_parser.add_argument("input", nargs="?", default="embeddings.jsonl")

    query_parser = subparsers.add_parser("query", help="Query Chroma by text")
    query_parser.add_argument("query_text", help="Natural language query")
    query_parser.add_argument("--n-results", type=int, default=5, help="Number of results (default: 5)")

    args = parser.parse_args()
    if args.command == "ingest":
        ingest(args.input)
    elif args.command == "query":
        query(args.query_text, args.n_results)