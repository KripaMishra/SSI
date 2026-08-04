import json
from pathlib import Path
import chromadb
from src.internal.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_client():
    if settings.chroma_api_key:
        kwargs = {"api_key": settings.chroma_api_key}
        if settings.chroma_tenant:
            kwargs["tenant"] = settings.chroma_tenant
        if settings.chroma_database:
            kwargs["database"] = settings.chroma_database
        if settings.chroma_cloud_host:
            kwargs["cloud_host"] = settings.chroma_cloud_host
            kwargs["cloud_port"] = settings.chroma_cloud_port
        logger.debug("creating Chroma cloud client", extra={"tenant": settings.chroma_tenant, "database": settings.chroma_database})
        return chromadb.CloudClient(**kwargs)
    local_path = Path(settings.chroma_local_path)
    local_path.mkdir(parents=True, exist_ok=True)
    logger.debug("creating Chroma local client", extra={"path": str(local_path)})
    return chromadb.PersistentClient(path=str(local_path))


def get_collection(client, name: str | None = None):
    name = name or settings.chroma_collection
    try:
        coll = client.get_collection(name)
        logger.debug("found existing collection", extra={"collection": name})
        return coll
    except ValueError:
        coll = client.create_collection(name)
        logger.info("created collection", extra={"collection": name})
        return coll


def query_chroma(query_text: str, n_results: int = 5) -> list[dict]:
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set")
        raise ValueError("GEMINI_API_KEY not set in .env")

    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)
    logger.debug("embedding query text", extra={"query_length": len(query_text)})
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=query_text,
        config={"output_dimensionality": settings.embedding_dimensions},
    )
    query_embedding = result.embeddings[0].values
    logger.debug("query embedding generated", extra={"dims": len(query_embedding)})

    chroma_client = get_client()
    collection = get_collection(chroma_client)

    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    logger.debug("Chroma query executed", extra={"n_results": len(results["documents"][0])})

    out = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        out.append({
            "document": doc,
            "metadata": {k: v for k, v in meta.items()},
            "distance": float(dist),
            "source": "vector_db",
            "collection": settings.chroma_collection,
        })
    return out


def ingest_chroma(input_path: str) -> int:
    logger.info("ingesting embeddings into Chroma", extra={"input": input_path})
    client = get_client()
    collection = get_collection(client)

    with open(input_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    logger.info("loaded embeddings records", extra={"count": len(records)})

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for rec in records:
        ids.append(rec["id"])
        embeddings.append(rec["embedding"])
        documents.append(rec["text"])
        metadata = {
            "category": rec["metadata"]["category"],
            "ref": rec["metadata"]["ref"],
            "tags": ",".join(rec["metadata"]["tags"]),
        }
        if rec["metadata"].get("attributes"):
            metadata["attributes"] = json.dumps(rec["metadata"]["attributes"])
        metadatas.append(metadata)

    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    logger.info("Chroma ingest complete", extra={"count": len(ids)})
    return len(ids)