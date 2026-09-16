import os
import sys
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("UNIT_TESTS", "1")

from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from src.api.main import app, _cache
from src.agent.models import AgentResponse
from src.queue import store as store_module
from src.queue.config import QUEUE_NAME

client = TestClient(app)

TOKEN = "test-secret-token"


def _mock_agent_response() -> AgentResponse:
    return AgentResponse(
        answer="Auth test answer.",
        intent="WHAT",
        citations=[],
        confidence=0.9,
        status="OK",
    )


class _AuthTestCase(TestCase):
    """Base: auth tests patch API_AUTH_TOKEN, mock the agent, and use fake Redis.

    /ask-direct is patched so nothing hits the live agent; /ask, /tasks/{id}
    and /cache/invalidate use fakeredis for the cache and the task store (see
    tests/test_api.py for the same pattern).
    """

    TOKEN = ""

    def setUp(self):
        self.token_patch = patch("src.api.main.API_AUTH_TOKEN", self.TOKEN)
        self.token_patch.start()
        self.agent_patch = patch("src.api.main.run_agent", return_value=_mock_agent_response())
        self.agent_patch.start()

        self.fake_redis = FakeStrictRedis(decode_responses=True)
        _cache._client = self.fake_redis
        store_module.task_store._client = self.fake_redis
        self.api_mod = sys.modules["src.api.main"]

    def tearDown(self):
        self.fake_redis.flushall()
        _cache._client = None
        store_module.task_store._client = None
        self.agent_patch.stop()
        self.token_patch.stop()


class TestApiAuthEnabled(_AuthTestCase):
    TOKEN = TOKEN

    def test_ask_direct_missing_key_rejected(self):
        response = client.post("/ask-direct", json={"question": "test"})
        self.assertEqual(response.status_code, 401)

    def test_ask_direct_wrong_key_rejected(self):
        response = client.post(
            "/ask-direct", json={"question": "test"}, headers={"X-API-Key": "wrong-key"}
        )
        self.assertEqual(response.status_code, 401)

    def test_ask_direct_non_ascii_key_rejected_not_500(self):
        # Raw header bytes are latin-1 decoded by the server; compare_digest
        # raises TypeError on non-ASCII str, so this must 401, never 500.
        response = client.post(
            "/ask-direct", json={"question": "test"}, headers={"X-API-Key": b"\xff\xfe"}
        )
        self.assertEqual(response.status_code, 401)

    def test_ask_direct_correct_key_accepted(self):
        response = client.post(
            "/ask-direct", json={"question": "test"}, headers={"X-API-Key": TOKEN}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Auth test answer.")

    def test_ask_missing_key_rejected(self):
        # 401 fires before any task is enqueued
        response = client.post("/ask", json={"question": "test"})
        self.assertEqual(response.status_code, 401)

    def test_task_status_missing_key_rejected(self):
        response = client.get("/tasks/some-task-id")
        self.assertEqual(response.status_code, 401)

    def test_task_status_correct_key_accepted(self):
        store_module.task_store.create("known-task", "run_agent_task", QUEUE_NAME)
        response = client.get("/tasks/known-task", headers={"X-API-Key": TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "QUEUED")

    def test_cache_invalidate_missing_key_rejected(self):
        response = client.post("/cache/invalidate")
        self.assertEqual(response.status_code, 401)

    def test_cache_invalidate_correct_key_accepted(self):
        response = client.post("/cache/invalidate", headers={"X-API-Key": TOKEN})
        self.assertEqual(response.status_code, 200)


class TestApiAuthDisabled(_AuthTestCase):
    TOKEN = ""

    def test_no_key_required_ask_direct(self):
        response = client.post("/ask-direct", json={"question": "test"})
        self.assertEqual(response.status_code, 200)

    def test_no_key_required_cache_invalidate(self):
        response = client.post("/cache/invalidate")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    main()
