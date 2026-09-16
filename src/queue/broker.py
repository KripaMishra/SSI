import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import CurrentMessage

from src.queue.config import QUEUE_REDIS_URL
from src.queue.middleware import TaskTrackingMiddleware


def _build_broker():
    # UNIT_TESTS=1 swaps in the in-memory broker so the suite needs no Redis.
    if os.getenv("UNIT_TESTS") == "1":
        return StubBroker()
    return RedisBroker(url=QUEUE_REDIS_URL, namespace="ssi")


broker = _build_broker()
broker.add_middleware(TaskTrackingMiddleware())
broker.add_middleware(CurrentMessage())
dramatiq.set_broker(broker)
