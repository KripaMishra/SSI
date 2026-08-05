from src.internal.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_EMBEDDING_CACHE: dict[str, list[float]] = {}


def get_embedding(text: str) -> list[float]:
    if text in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[text]

    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=text,
        config={"output_dimensionality": settings.embedding_dimensions},
    )
    embedding = result.embeddings[0].values
    _EMBEDDING_CACHE[text] = embedding
    logger.debug("embedding generated", extra={"dims": len(embedding), "text_preview": text[:80]})
    return embedding