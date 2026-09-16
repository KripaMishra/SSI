# ADR-003: QStash over RQ for the request queue

## Status

Accepted (the queue was reworked to QStash mid-development; see APPROACH.md limitation #8).

## Context

`POST /ask` receives a question and must return quickly while the agent runs for
tens of seconds to minutes. An asynchronous queue is required: accept the request,
process it in the background, and let the client poll for the result. The system
initially planned on `python-rq` (`task_plan.md`), then reworked to QStash during
development before any RQ implementation shipped (limitation #8 in APPROACH.md).
The team operates a managed deployment (Vercel/FastAPI) where running a
persistent worker process is friction.

## Decision

Use **QStash** as the message queue:

1. Client → FastAPI `POST /ask`; on cache miss, FastAPI enqueues the question and
   returns `202 Accepted` with a `message_id`.
2. QStash delivers to `/webhook/process`, which verifies the `Upstash-Signature`
   before running the agent.
3. The agent result is stored in Redis as `qstash_result:{id}` with a TTL; the
   client polls until available.
4. On completion the response is written to the semantic cache (see ADR-004).

## Consequences

- **Positive**: fully managed queue — no worker process to deploy or supervise;
  built-in retries and signature verification; fits the serverless webhook model.
- **Negative**: external vendor dependency (QStash + Upstash); result TTL means
  slow questions can expire before the client polls; the mid-development migration
  burned AI credits and prevented dedicated review loops (APPROACH.md #8–9).

## Alternatives considered

- **`python-rq`** (planned choice): rejected/replaced — requires a self-hosted
  worker process and Redis supervision; harder on a managed deployment.
- **Celery**: rejected — far heavier than needed for one queue.
- **Synchronous processing in the request**: rejected — blocks the client for the
  full agent runtime and risks platform timeouts.
