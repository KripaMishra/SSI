import hashlib
import os
import sys
import time
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("UNIT_TESTS", "1")

from dramatiq import Worker
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from src.agent.models import AgentResponse
from src.api.main import app, _cache
from src.queue import store as store_module
from src.queue.broker import broker
from src.queue.config import QUEUE_NAME

client = TestClient(app)

TIMEOUT = 75


def _mock_agent_response(question: str) -> AgentResponse:
    q = question.lower()
    if "sparkclean" in q and "spike" in q:
        return AgentResponse(
            answer="The SparkClean 1kg primary sales spike was driven by a 15% price-off promotion in Modern Trade during the week.",
            intent="WHY",
            citations=["Data/sales_primary_2025-09-16.csv"],
            confidence=0.97,
            status="OK",
        )
    if "glucojoy" in q or "glucoj" in q:
        return AgentResponse(
            answer="GlucoJoy is a glucose monitoring product. There was a stockout in Mumbai last quarter.",
            intent="WHAT",
            citations=["Data/inventory_2025.csv"],
            confidence=0.92,
            status="OK",
        )
    return AgentResponse(
        answer="I don't have enough data to answer that question.",
        intent="OUT_OF_DOMAIN",
        citations=[],
        confidence=0.1,
        status="ABSTAINED",
    )


def _mock_embedding(text: str) -> list[float]:
    """Deterministic stand-in for the Gemini embedding call."""
    return [byte / 255 for byte in hashlib.sha256(text.encode()).digest()[:8]]


class TestUi(TestCase):
    def test_root_serves_test_ui(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sales Intelligence Agent", response.text)


class TestCors(TestCase):
    def test_ask_direct_preflight(self):
        response = client.options(
            "/ask-direct",
            headers={
                "Origin": "http://127.0.0.1:5500",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "*")
        self.assertIn("POST", response.headers["access-control-allow-methods"])

    def test_task_polling_preflight(self):
        response = client.options(
            "/tasks/some-id",
            headers={
                "Origin": "http://127.0.0.1:5500",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("GET", response.headers["access-control-allow-methods"])


class TestAskDirect(TestCase):
    def _ask(self, question: str):
        start = time.time()
        response = client.post("/ask-direct", json={"question": question}, timeout=TIMEOUT)
        elapsed = time.time() - start
        print(f"\n=== RESPONSE ({elapsed:.1f}s) ===")
        print(f"status: {response.status_code}")
        data = response.json()
        for k, v in data.items():
            print(f"  {k}: {v}")
        print("=== END ===\n")
        return response, data

    def test_sparkclean_mumbai_spike(self):
        q = "Why did SparkClean 1kg primary sales spike in Mumbai in the week of 16 Sep 2025?"
        response, data = self._ask(q)
        self.assertEqual(response.status_code, 200)
        self.assertIn(data["status"], ("OK", "PENDING_APPROVAL", "ABSTAINED", "ERROR"))

    def test_glucojoy_stockout(self):
        q = "what is glucojoy?"
        response, data = self._ask(q)
        self.assertEqual(response.status_code, 200)
        self.assertIn(data["status"], ("OK", "PENDING_APPROVAL", "ABSTAINED", "ERROR"))


class _TaskTestCase(TestCase):
    """Base: fake Redis for cache + task store, and stubbed embeddings."""

    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        _cache._client = self.fake_redis
        store_module.task_store._client = self.fake_redis
        broker.flush_all()
        self.embed_patcher = patch("src.cache.cache.get_embedding", side_effect=_mock_embedding)
        self.embed_patcher.start()

    def tearDown(self):
        self.embed_patcher.stop()
        self.fake_redis.flushall()
        _cache._client = None
        store_module.task_store._client = None


class _WorkerTestCase(_TaskTestCase):
    """Adds an in-process worker, so queued tasks actually run during the test."""

    @classmethod
    def setUpClass(cls):
        cls.worker = Worker(broker, worker_timeout=100)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.worker.stop()


class TestAskEndpoint(_TaskTestCase):
    def test_ask_cache_hit(self):
        """When cache has the answer, /ask returns it without enqueuing"""
        expected = AgentResponse(
            answer="Cached promotion answer",
            intent="WHY",
            citations=["test"],
            confidence=0.99,
            status="OK",
        )
        _cache.set("Why did sales spike?", expected)

        response = client.post("/ask", json={"question": "Why did sales spike?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], expected.answer)

    def test_ask_miss_enqueues_a_task(self):
        """On a cache miss /ask returns 202 with the task id and the task is only queued"""
        response = client.post("/ask", json={"question": "Why did SparkClean spike?"})

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "QUEUED")
        self.assertTrue(body["task_id"])

        record = store_module.task_store.get(body["task_id"])
        self.assertEqual(record["status"], "QUEUED")
        self.assertEqual(record["actor"], "run_agent_task")
        self.assertEqual(record["queue"], QUEUE_NAME)


class TestTaskStatus(_WorkerTestCase):
    def test_task_completes_and_exposes_the_agent_response(self):
        """The worker runs the queued task and its result is readable from /tasks/{id}"""
        question = "Why did SparkClean spike?"
        agent_resp = _mock_agent_response(question)

        with patch("src.queue.actors.run_agent", return_value=agent_resp):
            posted = client.post("/ask", json={"question": question})
            self.assertEqual(posted.status_code, 202)
            task_id = posted.json()["task_id"]

            broker.join(QUEUE_NAME)
            self.worker.join()

        status = client.get(f"/tasks/{task_id}")
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["result"]["response"]["answer"], agent_resp.answer)
        self.assertEqual(body["result"]["response"]["intent"], agent_resp.intent)
        self.assertIsNotNone(body["started_at"])
        self.assertIsNotNone(body["finished_at"])
        self.assertIsNone(body["error"])

    def test_unknown_task_returns_404(self):
        response = client.get("/tasks/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown task id", response.json()["detail"])


if __name__ == "__main__":
    main()
