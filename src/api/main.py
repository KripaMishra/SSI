import json
import os
import time
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

import redis
from qstash.client import QStash
from qstash.receiver import Receiver

from dotenv import load_dotenv
load_dotenv()

from src.agent.models import AgentResponse
from src.agent.graph import run_agent, AgentTimeoutError
from src.agent.config import agent_config
from src.cache.cache import (
    SemanticCache,
    UPSTASH_REDIS_URL,
    CACHE_TTL,
    QUEUE_NAME,
    QSTASH_WEBHOOK_PATH,
    QSTASH_POLL_INTERVAL,
    QSTASH_JOB_TIMEOUT,
    QSTASH_RESULT_KEY_PREFIX,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

_cache = SemanticCache()

_redis_conn = redis.Redis.from_url(UPSTASH_REDIS_URL, decode_responses=True)
_qstash = QStash(token=os.getenv("QSTASH_TOKEN"))
_receiver = None
_QSTASH_SIGNING_KEYS_FETCHED = False


def _get_receiver():
    global _receiver, _QSTASH_SIGNING_KEYS_FETCHED
    if _receiver is not None:
        return _receiver
    if not _QSTASH_SIGNING_KEYS_FETCHED:
        _QSTASH_SIGNING_KEYS_FETCHED = True
        try:
            keys = _qstash.signing_key.get()
            current_key = keys.current
            next_key = keys.next
            logger.info("signing keys fetched from QStash API")
        except Exception as exc:
            current_key = os.getenv("QSTASH_CURRENT_SIGNING_KEY")
            next_key = os.getenv("QSTASH_NEXT_SIGNING_KEY")
            logger.warning("failed to fetch signing keys, using env fallback", extra={"error": str(exc)})
        _receiver = Receiver(current_signing_key=current_key, next_signing_key=next_key)
    return _receiver

app = FastAPI(title="SSI Agent API")


class AskRequest(BaseModel):
    question: str


class ErrorResponse(BaseModel):
    detail: str


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    body = await request.body()
    logger.info("incoming request", extra={
        "method": request.method,
        "path": request.url.path,
        "body": body.decode("utf-8", errors="replace")[:500],
    })
    try:
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info("request completed", extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "elapsed_ms": round(elapsed * 1000, 1),
        })
        return response
    except Exception:
        elapsed = time.time() - start
        logger.exception("request failed", extra={
            "method": request.method,
            "path": request.url.path,
            "elapsed_ms": round(elapsed * 1000, 1),
        })
        raise


@app.post("/ask", response_model=AgentResponse)
def ask(ask_req: AskRequest, fast_req: Request):
    logger.info("processing /ask", extra={"question": ask_req.question[:200]})

    cached = _cache.get(ask_req.question)
    if cached is not None:
        logger.info("/ask cache HIT", extra={"status": cached.status, "intent": cached.intent})
        return cached

    logger.info("enqueuing to QStash", extra={"queue": QUEUE_NAME})

    base_url = os.getenv("QSTASH_WEBHOOK_BASE_URL") or str(fast_req.base_url).rstrip("/")
    webhook_url = base_url + QSTASH_WEBHOOK_PATH

    result = _qstash.message.enqueue_json(
        queue=QUEUE_NAME,
        url=webhook_url,
        body={"question": ask_req.question},
        retries=1,
        timeout=str(QSTASH_JOB_TIMEOUT) + "s",
    )

    message_id = result.message_id
    result_key = QSTASH_RESULT_KEY_PREFIX + message_id

    logger.info("waiting for QStash result", extra={"message_id": message_id, "result_key": result_key})

    deadline = time.time() + QSTASH_JOB_TIMEOUT
    while time.time() < deadline:
        time.sleep(QSTASH_POLL_INTERVAL)
        raw = _redis_conn.get(result_key)
        if raw is not None:
            data = json.loads(raw)
            if data.get("error"):
                logger.error("QStash webhook reported error", extra={"message_id": message_id, "error": data["error"]})
                raise HTTPException(status_code=500, detail=f"Agent execution failed: {data['error']}")
            response = AgentResponse(**data["response"])
            _cache.set(ask_req.question, response)
            logger.info("/ask response", extra={
                "status": response.status,
                "intent": response.intent,
                "confidence": response.confidence,
                "cached": True,
            })
            _redis_conn.delete(result_key)
            return response

    logger.warning("/ask timeout waiting for QStash result", extra={
        "question": ask_req.question[:200],
        "message_id": message_id,
    })
    raise HTTPException(status_code=408, detail="Agent did not respond within the timeout period")


@app.post("/webhook/process")
async def process_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("Upstash-Signature", "")

    try:
        _get_receiver().verify(
            signature=signature,
            body=raw_body.decode("utf-8"),
        )
    except Exception as e:
        logger.warning("QStash signature verification failed", extra={"error": str(e)})
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    question = body.get("question", "")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' in body")

    message_id = request.headers.get("Upstash-Message-Id", "unknown")
    result_key = QSTASH_RESULT_KEY_PREFIX + message_id

    logger.info("webhook processing question", extra={"message_id": message_id, "question_preview": question[:200]})

    try:
        agent_response = run_agent(question, agent_config)
        payload = {
            "response": json.loads(agent_response.model_dump_json()),
        }
        _redis_conn.set(result_key, json.dumps(payload))
        _redis_conn.expire(result_key, CACHE_TTL)
        logger.info("webhook completed", extra={
            "message_id": message_id,
            "intent": agent_response.intent,
            "confidence": agent_response.confidence,
        })
        return {"ok": True}
    except AgentTimeoutError:
        logger.warning("webhook agent timeout", extra={"message_id": message_id})
        _redis_conn.set(result_key, json.dumps({"error": "Agent did not respond within the timeout period"}))
        _redis_conn.expire(result_key, CACHE_TTL)
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        logger.exception("webhook agent failed", extra={"message_id": message_id})
        _redis_conn.set(result_key, json.dumps({"error": str(e)}))
        _redis_conn.expire(result_key, CACHE_TTL)
        return {"ok": False, "error": str(e)}


@app.post("/cache/invalidate")
def invalidate_cache():
    """Invalidate all semantic cache entries. Call on data update events.

    ponytail: no auth yet — webhook signature verification is QStash-specific;
    #11 adds API auth for all endpoints.
    """
    _cache.clear()
    logger.info("semantic cache invalidated")
    return {"ok": True}


@app.post("/ask-direct", response_model=AgentResponse)
def ask_direct(request: AskRequest):
    logger.info("processing /ask-direct", extra={"question": request.question[:200]})
    try:
        response = run_agent(request.question, agent_config)
        logger.info("/ask-direct response", extra={
            "status": response.status,
            "intent": response.intent,
            "confidence": response.confidence,
        })
        return response
    except AgentTimeoutError:
        logger.warning("/ask-direct timeout", extra={"question": request.question[:200]})
        raise HTTPException(status_code=408, detail="Agent did not respond within the timeout period")
    except Exception:
        logger.exception("run_agent failed", extra={"question": request.question[:200]})
        raise HTTPException(status_code=500, detail="Agent execution failed")