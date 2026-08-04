import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import argparse
from google import genai
from src.internal.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_embeddings(input_path: str, output_path: str) -> None:
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set in .env")
        raise ValueError("GEMINI_API_KEY not set in .env")

    client = genai.Client(api_key=settings.gemini_api_key)

    with open(input_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    logger.info("loaded records", extra={"input": input_path, "count": len(records)})

    output_lines = []
    for idx, rec in enumerate(records):
        text = rec["text"]
        logger.debug("embedding record", extra={"index": idx, "doc_id": rec.get("id", "?"), "text_length": len(text)})
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config={"output_dimensionality": settings.embedding_dimensions},
        )
        embedding = result.embeddings[0].values
        logger.debug("embedding generated", extra={"index": idx, "dims": len(embedding)})
        rec["embedding"] = embedding
        output_lines.append(json.dumps(rec, ensure_ascii=False))

    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    output_path_obj.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    logger.info("embeddings written", extra={"output": output_path, "count": len(output_lines)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate embeddings via Gemini")
    parser.add_argument("input", nargs="?", default="cleaned/cleaned_docs.jsonl")
    parser.add_argument("output", nargs="?", default="embeddings.jsonl")
    args = parser.parse_args()
    generate_embeddings(args.input, args.output)
