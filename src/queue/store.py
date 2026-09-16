import json
import time
from typing import Any, Optional

import redis as redis_lib

from src.queue.config import QUEUE_REDIS_URL, TASK_KEY_PREFIX, TASK_TTL_SECONDS
from src.utils.logger import get_logger

logger = get_logger(__name__)

STATUS_QUEUED = "QUEUED"
STATUS_RUNNING = "RUNNING"
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILURE = "FAILURE"


def _as_float(value) -> Optional[float]:
    try:
        return float(value) if value else None
    except (TypeError, ValueError):
        return None


class TaskStore:
    """One Redis hash per queued API call, keyed by task id (the Dramatiq message id)."""

    def __init__(self, redis_url: str | None = None, redis_client=None):
        self._redis_url = redis_url or QUEUE_REDIS_URL
        self._client: redis_lib.Redis | None = redis_client

    @property
    def client(self):
        if self._client is None:
            self._client = redis_lib.Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def _key(self, task_id: str) -> str:
        return TASK_KEY_PREFIX + task_id

    def create(self, task_id: str, actor: str, queue: str) -> None:
        key = self._key(task_id)
        self.client.hset(key, mapping={
            "task_id": task_id,
            "actor": actor,
            "queue": queue,
            "status": STATUS_QUEUED,
            "attempts": 1,
            "created_at": str(time.time()),
        })
        self.client.expire(key, TASK_TTL_SECONDS)
        logger.info("task queued", extra={"task_id": task_id, "actor": actor, "queue": queue})

    def mark_running(self, task_id: str) -> None:
        self._update(task_id, {"status": STATUS_RUNNING, "started_at": str(time.time())})

    def mark_success(self, task_id: str) -> None:
        # Keeps any result the actor already recorded.
        self._update(task_id, {
            "status": STATUS_SUCCESS,
            "finished_at": str(time.time()),
            "error": "",
        })

    def set_result(self, task_id: str, result: Any) -> None:
        self._update(task_id, {"result": json.dumps(result, default=str)})

    def mark_failure(self, task_id: str, error: str) -> None:
        self._update(task_id, {
            "status": STATUS_FAILURE,
            "finished_at": str(time.time()),
            "error": error,
        })

    def mark_queued(self, task_id: str) -> None:
        """A failed attempt that still has retries left goes back to QUEUED."""
        key = self._key(task_id)
        if not self.client.exists(key):
            return
        self._update(task_id, {
            "status": STATUS_QUEUED,
            "started_at": "",
            "finished_at": "",
            "error": "",
        })
        self.client.hincrby(key, "attempts", 1)

    def get(self, task_id: str) -> Optional[dict]:
        raw = self.client.hgetall(self._key(task_id))
        if not raw:
            return None
        return {
            "task_id": raw.get("task_id", task_id),
            "actor": raw.get("actor", ""),
            "queue": raw.get("queue", ""),
            "status": raw.get("status", STATUS_QUEUED),
            "attempts": int(raw.get("attempts", 1)),
            "created_at": _as_float(raw.get("created_at")),
            "started_at": _as_float(raw.get("started_at")),
            "finished_at": _as_float(raw.get("finished_at")),
            "result": json.loads(raw["result"]) if raw.get("result") else None,
            "error": raw.get("error") or None,
        }

    def _update(self, task_id: str, fields: dict) -> None:
        key = self._key(task_id)
        if not self.client.exists(key):
            return
        self.client.hset(key, mapping=fields)
        self.client.expire(key, TASK_TTL_SECONDS)


task_store = TaskStore()
