import time
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from src.agent.models import AgentResponse
from src.agent.graph import run_agent, AgentTimeoutError
from src.agent.config import agent_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="SSI Agent API")


class AskRequest(BaseModel):
    question: str


class ErrorResponse(BaseModel):
    detail: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    body = await request.body()
    logger.info("incoming request", extra={"method": request.method, "path": request.url.path, "body": body.decode("utf-8", errors="replace")[:500]})
    try:
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info("request completed", extra={"method": request.method, "path": request.url.path, "status": response.status_code, "elapsed_ms": round(elapsed * 1000, 1)})
        return response
    except Exception:
        elapsed = time.time() - start
        logger.exception("request failed", extra={"method": request.method, "path": request.url.path, "elapsed_ms": round(elapsed * 1000, 1)})
        raise


@app.post("/ask", response_model=AgentResponse)
def ask(request: AskRequest):
    logger.info("processing /ask", extra={"question": request.question[:200]})
    try:
        response = run_agent(request.question, agent_config)
        logger.info("/ask response", extra={"status": response.status, "intent": response.intent, "confidence": response.confidence})
        return response
    except AgentTimeoutError:
        logger.warning("/ask timeout", extra={"question": request.question[:200]})
        raise HTTPException(status_code=408, detail="Agent did not respond within the timeout period")
    except Exception:
        logger.exception("run_agent failed", extra={"question": request.question[:200]})
        raise HTTPException(status_code=500, detail="Agent execution failed")