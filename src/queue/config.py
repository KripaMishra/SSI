import os

from dotenv import load_dotenv
load_dotenv()

QUEUE_REDIS_URL = os.getenv("QUEUE_REDIS_URL") or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
QUEUE_NAME = os.getenv("QUEUE_NAME", "asks")
TASK_TTL_SECONDS = int(os.getenv("TASK_TTL_SECONDS", "3600"))
TASK_KEY_PREFIX = "task:"
