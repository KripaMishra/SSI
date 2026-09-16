import os
import sys
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("UNIT_TESTS", "1")

from dramatiq import Worker
from fakeredis import FakeStrictRedis

from src.agent.models import AgentResponse
from src.queue import store as store_module
from src.queue.actors import run_agent_task
from src.queue.broker import broker
from src.queue.config import QUEUE_NAME, TASK_KEY_PREFIX, TASK_TTL_SECONDS
from src.queue.store import (
    STATUS_FAILURE,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    TaskStore,
)


def _response(answer: str = "Because of the promotion.") -> AgentResponse:
    return AgentResponse(
        answer=answer,
        intent="WHY",
        citations=["relational_db:promotions"],
        confidence=0.93,
        status="OK",
    )


class TestTaskStore(TestCase):
    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        self.store = TaskStore(redis_client=self.fake_redis)

    def tearDown(self):
        self.fake_redis.flushall()

    def test_create_records_a_queued_task(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)

        record = self.store.get("task-1")
        self.assertEqual(record["task_id"], "task-1")
        self.assertEqual(record["actor"], "run_agent_task")
        self.assertEqual(record["queue"], QUEUE_NAME)
        self.assertEqual(record["status"], STATUS_QUEUED)
        self.assertEqual(record["attempts"], 1)
        self.assertIsNotNone(record["created_at"])
        self.assertIsNone(record["started_at"])
        self.assertIsNone(record["finished_at"])
        self.assertIsNone(record["result"])
        self.assertIsNone(record["error"])

    def test_create_sets_a_ttl(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)

        ttl = self.fake_redis.ttl(TASK_KEY_PREFIX + "task-1")
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, TASK_TTL_SECONDS)

    def test_mark_running(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)
        self.store.mark_running("task-1")

        record = self.store.get("task-1")
        self.assertEqual(record["status"], STATUS_RUNNING)
        self.assertIsNotNone(record["started_at"])

    def test_set_result_is_kept_by_mark_success(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)
        self.store.set_result("task-1", {"response": _response().model_dump()})
        self.store.mark_success("task-1")

        record = self.store.get("task-1")
        self.assertEqual(record["status"], STATUS_SUCCESS)
        self.assertEqual(record["result"]["response"]["answer"], "Because of the promotion.")
        self.assertIsNotNone(record["finished_at"])
        self.assertIsNone(record["error"])

    def test_mark_failure_stores_the_error(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)
        self.store.mark_failure("task-1", "Agent did not respond within the timeout period")

        record = self.store.get("task-1")
        self.assertEqual(record["status"], STATUS_FAILURE)
        self.assertIn("timeout", record["error"])
        self.assertIsNotNone(record["finished_at"])

    def test_mark_queued_returns_a_retried_task_to_queued(self):
        self.store.create("task-1", "run_agent_task", QUEUE_NAME)
        self.store.mark_running("task-1")
        self.store.mark_failure("task-1", "transient boom")
        self.store.mark_queued("task-1")

        record = self.store.get("task-1")
        self.assertEqual(record["status"], STATUS_QUEUED)
        self.assertEqual(record["attempts"], 2)
        self.assertIsNone(record["started_at"])
        self.assertIsNone(record["error"])

    def test_get_unknown_task_returns_none(self):
        self.assertIsNone(self.store.get("does-not-exist"))

    def test_updates_to_an_unknown_task_do_not_create_a_record(self):
        self.store.mark_running("ghost")
        self.store.mark_success("ghost")
        self.store.set_result("ghost", {"response": {}})
        self.store.mark_failure("ghost", "boom")
        self.store.mark_queued("ghost")

        self.assertIsNone(self.store.get("ghost"))


class TestRunAgentTask(TestCase):
    """Drives the actor through an in-process worker on the stub broker."""

    @classmethod
    def setUpClass(cls):
        cls.worker = Worker(broker, worker_timeout=100)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.worker.stop()

    def setUp(self):
        self.fake_redis = FakeStrictRedis(decode_responses=True)
        store_module.task_store._client = self.fake_redis
        broker.flush_all()

    def tearDown(self):
        self.fake_redis.flushall()
        store_module.task_store._client = None

    def test_actor_is_registered_on_the_asks_queue(self):
        self.assertEqual(run_agent_task.queue_name, QUEUE_NAME)

    def test_successful_run_stores_the_agent_response(self):
        response = _response()
        with patch("src.queue.actors.run_agent", return_value=response):
            message = run_agent_task.send("Why did sales spike?")
            broker.join(QUEUE_NAME)
            self.worker.join()

        record = store_module.task_store.get(message.message_id)
        self.assertEqual(record["status"], STATUS_SUCCESS)
        self.assertEqual(record["actor"], "run_agent_task")
        self.assertEqual(record["result"]["response"]["answer"], response.answer)
        self.assertIsNotNone(record["started_at"])
        self.assertIsNotNone(record["finished_at"])

    def test_failed_run_is_recorded_as_failure(self):
        with patch("src.queue.actors.run_agent", side_effect=RuntimeError("agent exploded")):
            message = run_agent_task.send_with_options(
                args=("Why did sales spike?",), max_retries=0
            )
            with self.assertRaises(RuntimeError):
                broker.join(QUEUE_NAME)
            self.worker.join()

        record = store_module.task_store.get(message.message_id)
        self.assertEqual(record["status"], STATUS_FAILURE)
        self.assertIn("agent exploded", record["error"])


if __name__ == "__main__":
    main()
