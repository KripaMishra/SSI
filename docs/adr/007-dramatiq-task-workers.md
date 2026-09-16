# ADR-007: Dramatiq task workers for queued API calls

## Status

Accepted **on the `feat/dramatiq-task-workers` branch only** — deliberately *not* merged into
`main`. It supersedes [ADR-003](003-qstash-over-rq.md) on that branch; ADR-003 remains the
record of what `main` runs and is not reversed there. The two branches are co-existing
alternative implementations of the same service, not a migration.

## Context

`POST /ask` must accept a question quickly while the agent runs for tens of seconds. On `main`
that queue is QStash plus a signature-verified `/webhook/process` (ADR-003), a choice driven by
a serverless (Vercel) deployment where a long-running worker process is friction.

This branch targets a self-hosted deployment (Docker Compose) and requires something ADR-003
did not: an explicitly addressable unit of work per request. `/ask` on `main` returns
`AgentResponse` after blocking server-side on a Redis poll, and the QStash `message_id` is only
an internal handle — there is no way to ask "what is the state of that question?".

## Decision

Replace QStash with **Dramatiq** (Redis broker) and make **one queued API call = one task**:

1. `POST /ask` on a cache miss enqueues one `run_agent_task` on the `asks` queue and returns
   `202 {"task_id", "status": "QUEUED"}`. The `task_id` is the Dramatiq `message_id`.
2. `GET /tasks/{task_id}` reports `QUEUED` / `RUNNING` / `SUCCESS` (with the `AgentResponse`)
   / `FAILURE` (with the error), read from a Redis hash per task (`task:{id}`) that a
   `TaskTrackingMiddleware` keeps in step with the message lifecycle.
3. Workers run the whole agent pipeline for that task; the LLM turns, tool calls, embedding and
   SQL work stay *inside* the task. No subtask decomposition: the graph is strictly sequential,
   so extra tasks would only add queue round-trips, message serialization, and nested-waiting
   thread starvation.
4. `/ask-direct` still runs inline for synchronous use, and a cache hit still answers inline.
5. Docker Compose runs `redis`, `api`, and `worker`
   (`dramatiq src.queue.actors -Q asks -t 8`).

## Consequences

- **Positive**: the request is a first-class, addressable task with a status; no external
  queue vendor; the queue, the semantic cache and the task records share one Redis; worker
  concurrency and retry policy are ours to set; local development needs no public URL or
  signature verification.
- **Negative**: a worker process must be deployed and supervised (the friction ADR-003 cited);
  task records need a TTL to bound Redis growth (`TASK_TTL_SECONDS`, 1 hour); `main` and this
  branch now diverge, so fixes must be applied twice or merged deliberately.

## Alternatives considered

- **Keep QStash on this branch**: rejected for this deployment — signed webhooks need a public
  endpoint, and the QStash `message_id` cannot back a status API without extra state anyway.
- **Celery / RQ**: rejected again — same worker-process overhead with more machinery than needed
  for a single queue (see ADR-003).
- **Subtask per LLM/tool/embedding call**: rejected — it serializes LangChain messages over the
  broker, adds a round-trip per hop, and a parent blocking on children starves worker threads
  for no gain in throughput or isolation.
- **Dramatiq's `Results` middleware for results**: rejected — it stores only the final value,
  while the status endpoint also needs `QUEUED`/`RUNNING` and the failure string.
