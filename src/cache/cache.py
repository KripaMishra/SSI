import json
import time
import os
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import redis as redis_lib

from src.agent.models import AgentResponse
from src.cache.embedding import get_embedding
from src.utils.logger import get_logger

logger = get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "600"))
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.97"))
CACHE_KEY_PREFIX = "semcache:"
CACHE_INDEX_KEY = "semcache:index"

QUEUE_NAME = os.getenv("QSTASH_QUEUE_NAME", "ssi-asks")
QSTASH_WEBHOOK_PATH = os.getenv("QSTASH_WEBHOOK_PATH", "/webhook/process")
QSTASH_POLL_INTERVAL = float(os.getenv("QSTASH_POLL_INTERVAL", "0.5"))
QSTASH_JOB_TIMEOUT = int(os.getenv("QSTASH_JOB_TIMEOUT", "180"))
QSTASH_RESULT_KEY_PREFIX = "qstash_result:"

UPSTASH_REDIS_URL = os.getenv("REDIS_URL")
QSTASH_URL = os.getenv("QSTASH_URL")
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN")
QSTASH_CURRENT_SIGNING_KEY = os.getenv("QSTASH_CURRENT_SIGNING_KEY")
QSTASH_NEXT_SIGNING_KEY = os.getenv("QSTASH_NEXT_SIGNING_KEY")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    arr_a = np.array(a, dtype=np.float64)
    arr_b = np.array(b, dtype=np.float64)
    dot = np.dot(arr_a, arr_b)
    norm_a = np.linalg.norm(arr_a)
    norm_b = np.linalg.norm(arr_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class SemanticCache:
    def __init__(self, redis_url: str | None = None, redis_client=None):
        self._redis_url = redis_url or REDIS_URL
        self._client: redis_lib.Redis | None = redis_client

    @property
    def client(self):
        if self._client is None:
            self._client = redis_lib.Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def get(self, query: str) -> Optional[AgentResponse]:
        query_emb = get_embedding(query)
        cache_keys = self._get_active_keys()
        best_sim = 0.0
        best_entry = None
        for key in cache_keys:
            raw = self.client.hget(key, "response")
            emb_raw = self.client.hget(key, "embedding")
            if raw is None or emb_raw is None:
                continue
            try:
                cached_emb = json.loads(emb_raw)
                sim = _cosine_similarity(query_emb, cached_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_entry = (key, raw)
            except Exception:
                continue
        if best_sim >= CACHE_SIMILARITY_THRESHOLD and best_entry is not None:
            key, raw = best_entry
            self.client.expire(key, CACHE_TTL)
            logger.info("cache HIT", extra={"key": key, "similarity": round(best_sim, 4)})
            return AgentResponse(**json.loads(raw))
        logger.debug("cache MISS", extra={"best_similarity": round(best_sim, 4)})
        return None

    def set(self, query: str, response: AgentResponse) -> None:
        embedding = get_embedding(query)
        key = CACHE_KEY_PREFIX + str(hash(query))
        self.client.hset(key, mapping={
            "query": query,
            "embedding": json.dumps(embedding),
            "response": response.model_dump_json(),
            "created_at": str(time.time()),
        })
        self.client.expire(key, CACHE_TTL)
        self.client.sadd(CACHE_INDEX_KEY, key)
        logger.info("cache SET", extra={"key": key, "ttl": CACHE_TTL})

    def _get_active_keys(self) -> list[str]:
        return list(self.client.smembers(CACHE_INDEX_KEY))

    def clear(self) -> None:
        keys = self._get_active_keys()
        if keys:
            self.client.delete(*keys)
        self.client.delete(CACHE_INDEX_KEY)
        logger.info("cache cleared", extra={"removed": len(keys)})