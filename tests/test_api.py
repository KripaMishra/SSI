import json
import os
import sys
import time
from unittest import TestCase, main
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from src.api.main import app, _cache, _redis_conn, _qstash
from src.agent.models import AgentResponse

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


class TestUi(TestCase):
    def test_root_serves_test_ui(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SALES INTELLIGENCE", response.text)


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


class TestWebhookProcess(TestCase):
    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        _cache._client = self.fake_redis

        import src.api.main as api_mod
        self._orig_redis = api_mod._redis_conn
        api_mod._redis_conn = self.fake_redis

    def tearDown(self):
        self.fake_redis.flushall()
        import src.api.main as api_mod
        api_mod._redis_conn = self._orig_redis
        _cache._client = None

    def test_webhook_missing_signature(self):
        response = client.post("/webhook/process", json={"question": "test"})
        self.assertEqual(response.status_code, 401)

    def test_webhook_missing_question(self):
        with patch("src.api.main._get_receiver") as mock_get_rec:
            mock_rec = MagicMock()
            mock_get_rec.return_value = mock_rec
            response = client.post(
                "/webhook/process",
                json={},
                headers={"Upstash-Signature": "valid_sig"},
            )
            self.assertEqual(response.status_code, 400)

    def test_webhook_success_stores_result(self):
        question = "Why did SparkClean 1kg spike?"
        agent_resp = _mock_agent_response(question)

        with patch("src.api.main._get_receiver") as mock_get_rec, \
             patch("src.api.main.run_agent", return_value=agent_resp):
            mock_rec = MagicMock()
            mock_get_rec.return_value = mock_rec
            response = client.post(
                "/webhook/process",
                json={"question": question},
                headers={
                    "Upstash-Signature": "valid_sig",
                    "Upstash-Message-Id": "msg-001",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["ok"])

            raw = self.fake_redis.get("qstash_result:msg-001")
            self.assertIsNotNone(raw)
            data = json.loads(raw)
            self.assertEqual(data["response"]["answer"], agent_resp.answer)
            self.assertEqual(data["response"]["intent"], agent_resp.intent)

    def test_webhook_failure_stores_error(self):
        with patch("src.api.main._get_receiver") as mock_get_rec, \
             patch("src.api.main.run_agent", side_effect=Exception("Agent crashed")):
            mock_rec = MagicMock()
            mock_get_rec.return_value = mock_rec
            response = client.post(
                "/webhook/process",
                json={"question": "any question"},
                headers={
                    "Upstash-Signature": "valid_sig",
                    "Upstash-Message-Id": "msg-002",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["ok"])
            self.assertIn("Agent crashed", response.json()["error"])

            raw = self.fake_redis.get("qstash_result:msg-002")
            self.assertIsNotNone(raw)
            data = json.loads(raw)
            self.assertIn("Agent crashed", data["error"])

    def test_webhook_agent_timeout(self):
        from src.agent.graph import AgentTimeoutError
        with patch("src.api.main._get_receiver") as mock_get_rec, \
             patch("src.api.main.run_agent", side_effect=AgentTimeoutError()):
            mock_rec = MagicMock()
            mock_get_rec.return_value = mock_rec
            response = client.post(
                "/webhook/process",
                json={"question": "any question"},
                headers={
                    "Upstash-Signature": "valid_sig",
                    "Upstash-Message-Id": "msg-003",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["ok"])
            self.assertEqual(response.json()["error"], "timeout")


class TestAskEndpoint(TestCase):
    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        _cache._client = self.fake_redis

        import src.api.main as api_mod
        self._orig_redis = api_mod._redis_conn
        api_mod._redis_conn = self.fake_redis
        self.api_mod = api_mod

    def tearDown(self):
        self.fake_redis.flushall()
        self.api_mod._redis_conn = self._orig_redis
        _cache._client = None

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

    def test_ask_miss_enqueues_and_polls(self):
        """When cache misses, /ask enqueues to QStash and polls Redis for result"""
        question = "Why did SparkClean spike?"
        answer = "Because of promotion"

        mock_enqueue_resp = MagicMock()
        mock_enqueue_resp.message_id = "test-msg-001"
        mock_enqueue_resp.deduplicated = False

        # Set the result in Redis to simulate webhook completing
        result_key = "qstash_result:test-msg-001"
        payload = json.dumps({
            "response": {
                "answer": answer,
                "intent": "WHY",
                "citations": ["source"],
                "confidence": 0.95,
                "status": "OK",
            }
        })
        self.fake_redis.set(result_key, payload)
        self.fake_redis.expire(result_key, 600)

        with patch.object(_qstash.message, "enqueue_json", return_value=mock_enqueue_resp):
            response = client.post(
                "/ask",
                json={"question": question},
                headers={"host": "testserver"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["answer"], answer)

    def test_ask_miss_timeout(self):
        """When QStash message doesn't complete in time, /ask returns 408"""
        mock_enqueue_resp = MagicMock()
        mock_enqueue_resp.message_id = "test-msg-timeout"
        mock_enqueue_resp.deduplicated = False

        with patch.object(_qstash.message, "enqueue_json", return_value=mock_enqueue_resp), \
             patch("src.api.main.QSTASH_POLL_INTERVAL", 0.1), \
             patch("src.api.main.QSTASH_JOB_TIMEOUT", 1):

            response = client.post(
                "/ask",
                json={"question": "some question that won't be processed"},
                headers={"host": "testserver"},
            )
            self.assertEqual(response.status_code, 408)

    def test_ask_error_from_webhook(self):
        """When webhook stores error, /ask returns 500"""
        mock_enqueue_resp = MagicMock()
        mock_enqueue_resp.message_id = "test-msg-error"
        mock_enqueue_resp.deduplicated = False

        result_key = "qstash_result:test-msg-error"
        payload = json.dumps({"error": "Something went wrong"})
        self.fake_redis.set(result_key, payload)
        self.fake_redis.expire(result_key, 600)

        with patch.object(_qstash.message, "enqueue_json", return_value=mock_enqueue_resp):
            response = client.post(
                "/ask",
                json={"question": "broken question"},
                headers={"host": "testserver"},
            )
            self.assertEqual(response.status_code, 500)
            self.assertIn("Something went wrong", response.json()["detail"])

    def test_ask_caches_response_on_first_miss(self):
        """After /ask gets a response from webhook, it should be cached"""
        question = "First time question"
        answer = "First time answer"

        mock_enqueue_resp = MagicMock()
        mock_enqueue_resp.message_id = "test-msg-cache"
        mock_enqueue_resp.deduplicated = False

        result_key = "qstash_result:test-msg-cache"
        payload = json.dumps({
            "response": {
                "answer": answer,
                "intent": "WHAT",
                "citations": ["source"],
                "confidence": 0.9,
                "status": "OK",
            }
        })
        self.fake_redis.set(result_key, payload)
        self.fake_redis.expire(result_key, 600)

        with patch.object(_qstash.message, "enqueue_json", return_value=mock_enqueue_resp):
            response = client.post(
                "/ask",
                json={"question": question},
                headers={"host": "testserver"},
            )
            self.assertEqual(response.status_code, 200)

        response2 = client.post(
            "/ask",
            json={"question": question},
            headers={"host": "testserver"},
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2["answer"], answer)

    @patch.dict(os.environ, {"QSTASH_WEBHOOK_BASE_URL": "https://public.example.com"})
    def test_ask_uses_webhook_base_url_env(self):
        """When QSTASH_WEBHOOK_BASE_URL is set, it overrides the request base URL"""
        mock_enqueue_resp = MagicMock()
        mock_enqueue_resp.message_id = "test-msg-webhook-url"
        mock_enqueue_resp.deduplicated = False

        result_key = "qstash_result:test-msg-webhook-url"
        payload = json.dumps({
            "response": {
                "answer": "webhook url test",
                "intent": "WHAT",
                "citations": [],
                "confidence": 0.5,
                "status": "OK",
            }
        })
        self.fake_redis.set(result_key, payload)
        self.fake_redis.expire(result_key, 600)

        with patch.object(_qstash.message, "enqueue_json", return_value=mock_enqueue_resp) as mock_enqueue:
            response = client.post(
                "/ask",
                json={"question": "test webhook url"},
                headers={"host": "testserver"},
            )
            self.assertEqual(response.status_code, 200)
            # Verify the webhook URL used the env var, not the request base URL
            call_kwargs = mock_enqueue.call_args.kwargs
            self.assertEqual(call_kwargs["url"], "https://public.example.com/webhook/process")


if __name__ == "__main__":
    main()