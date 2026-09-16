import hmac
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from src.agent.config import agent_config
from src.agent.graph import AgentTimeoutError, run_agent
from src.agent.models import AgentResponse
from src.cache.cache import SemanticCache
from src.internal.settings import settings
from src.queue.actors import run_agent_task
from src.queue.config import QUEUE_NAME
from src.queue.store import task_store
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Empty = auth disabled (local dev). Read once at import; tests patch this
# module attribute directly.
API_AUTH_TOKEN = settings.api_auth_token


def require_api_key(x_api_key: str | None = Header(default=None)):
    """Reject requests without a valid X-API-Key when API_AUTH_TOKEN is set.

    Empty API_AUTH_TOKEN = auth disabled (local dev, no header needed).
    """
    if not API_AUTH_TOKEN:
        return
    # bytes, not str: compare_digest raises TypeError on non-ASCII str, and
    # header values (latin-1 decoded) or an env token with non-ASCII chars
    # would turn every auth check into a 500 instead of a 401.
    if x_api_key is None or not hmac.compare_digest(
        x_api_key.encode(), API_AUTH_TOKEN.encode()
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


_cache = SemanticCache()

app = FastAPI(title="SSI Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
_UI_PATH = Path(__file__).resolve().parents[2] / "ui" / "index.html"


class AskRequest(BaseModel):
    question: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    actor: str
    queue: str
    attempts: int
    created_at: float | None = None
    started_at: float | None = None
    finished_at: float | None = None
    result: dict | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    detail: str


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(_UI_PATH)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    body = await request.body()
    logger.info(
        "incoming request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "body": body.decode("utf-8", errors="replace")[:500],
        },
    )
    try:
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": round(elapsed * 1000, 1),
            },
        )
        return response
    except Exception:
        elapsed = time.time() - start
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "elapsed_ms": round(elapsed * 1000, 1),
            },
        )
        raise


@app.post("/ask")
def ask(ask_req: AskRequest, response: Response, _: None = Depends(require_api_key)):
    """Cache hit returns the answer inline; a cache miss queues one task and returns its id."""
    logger.info("processing /ask", extra={"question": ask_req.question[:200]})

    cached = _cache.get(ask_req.question)
    if cached is not None:
        logger.info(
            "/ask cache HIT", extra={"status": cached.status, "intent": cached.intent}
        )
        return cached

    message = run_agent_task.send(ask_req.question)
    response.status_code = 202
    logger.info(
        "task enqueued", extra={"task_id": message.message_id, "queue": QUEUE_NAME}
    )
    return {"task_id": message.message_id, "status": "QUEUED"}


@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str, _: None = Depends(require_api_key)):
    """Status of a queued task: QUEUED, RUNNING, SUCCESS (with result) or FAILURE (with error)."""
    record = task_store.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown task id")
    return record


@app.post("/cache/invalidate")
def invalidate_cache(_: None = Depends(require_api_key)):
    """Invalidate all semantic cache entries. Call on data update events.

    Protected by X-API-Key when API_AUTH_TOKEN is set.
    """
    _cache.clear()
    logger.info("semantic cache invalidated")
    return {"ok": True}


@app.post("/ask-direct", response_model=AgentResponse)
def ask_direct(request: AskRequest, _: None = Depends(require_api_key)):
    logger.info("processing /ask-direct", extra={"question": request.question[:200]})
    try:
        response = run_agent(request.question, agent_config)
        logger.info(
            "/ask-direct response",
            extra={
                "status": response.status,
                "intent": response.intent,
                "confidence": response.confidence,
            },
        )
        return response
    except AgentTimeoutError:
        logger.warning(
            "/ask-direct timeout", extra={"question": request.question[:200]}
        )
        raise HTTPException(
            status_code=408, detail="Agent did not respond within the timeout period"
        )
    except Exception:
        logger.exception("run_agent failed", extra={"question": request.question[:200]})
        raise HTTPException(status_code=500, detail="Agent execution failed")
