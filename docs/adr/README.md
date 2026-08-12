# Architecture Decision Records

Decision records for the SSI sales-intelligence assistant, derived from the
trade-offs and limitations in `APPROACH.md`, `ARTEFACT.md`, and
`docs/MODEL_BENCHMARK.md`.

## Index

| ADR | Title | Status | Summary |
|---|---|---|---|
| [001](001-single-agent-tool-loop.md) | Single-agent tool loop | Accepted | One LangGraph agent with a tool loop instead of multi-agent supervision — less latency, tokens, and state complexity (APPROACH.md §5, limitation #1). |
| [002](002-star-schema-and-null-with-flags.md) | Star schema + null-with-flag | Accepted | Star-schema data model; sentinel/negative unit values nulled and flagged via `sales_units_flag` instead of removed, keeping reconciliation auditable (APPROACH.md §0–2, ARTEFACT.md). |
| [003](003-qstash-over-rq.md) | QStash over RQ | Accepted | Managed QStash queue with webhook + signature verification replaced `python-rq` for the request queue (APPROACH.md §6, limitation #8). |
| [004](004-semantic-cache-ttl-threshold.md) | Semantic caching | Accepted | Redis semantic cache: cosine ≥ 0.97 match, 600s TTL with hot-cache promotion, explicit all-or-nothing invalidation (APPROACH.md §7, limitation #3). |
| [005](005-pii-redaction-pipeline.md) | PII redaction pipeline | Accepted | Deterministic redaction of phones/emails/names in the 30 unstructured docs before they reach the LLM and vector store (APPROACH.md §3, ARTEFACT.md). |
| [006](006-model-choice-deepseek-v4-flash.md) | Model choice | Accepted | `deepseek-v4-flash` stays default — benchmark beat fast-tier `kimi-k2.6` on accuracy (13/14 vs 12/14) and wall time (9.9 vs 16.4 min) (APPROACH.md limitation #4, MODEL_BENCHMARK.md). |
