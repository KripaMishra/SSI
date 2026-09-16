import dramatiq
from dramatiq.middleware import CurrentMessage

from src.agent.config import agent_config
from src.agent.graph import AGENT_TIMEOUT, AgentTimeoutError, run_agent
from src.queue.broker import broker  # noqa: F401 — sets the broker before the actor binds
from src.queue.config import QUEUE_NAME
from src.queue.store import task_store
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _current_task_id() -> str:
    message = CurrentMessage.get_current_message()
    return message.message_id if message is not None else ""


@dramatiq.actor(
    queue_name=QUEUE_NAME,
    max_retries=1,
    time_limit=AGENT_TIMEOUT * 1000 + 60_000,
    throws=(AgentTimeoutError,),
)
def run_agent_task(question: str) -> None:
    """One queued API call = one task: the whole agent pipeline for a question."""
    logger.info("run_agent_task start", extra={"question": question[:200]})
    response = run_agent(question, agent_config)
    task_store.set_result(_current_task_id(), {"response": response.model_dump()})
    logger.info("run_agent_task done", extra={
        "status": response.status,
        "intent": response.intent,
        "confidence": response.confidence,
    })
