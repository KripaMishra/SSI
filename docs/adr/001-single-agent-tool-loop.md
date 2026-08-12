# ADR-001: Single-agent tool loop over multi-agent supervision

## Status

Accepted (implemented in `src/agent/graph.py`).

## Context

The assistant must answer WHAT / WHY / WHAT_TO_DO questions over structured sales
data and unstructured documents. WHY answers require mandatory citations and
WHAT_TO_DO answers must return `PENDING_APPROVAL` status — both enforced by
`_validate_response()`. The question was whether one agent with a tool loop
suffices, or whether a multi-agent supervision architecture (planner, researcher,
reviewer) is warranted. Limitation #1 in APPROACH.md records this trade-off.

## Decision

Use a single agent with a tool loop (LangGraph `StateGraph`):

1. `llm_call` — model decides whether to call tools or answer directly.
2. `tool_node` — executes mounted tools (`search_docs`, `describe_database`,
   `query_database`) and returns results to the loop.
3. `finalize` — a second LLM invocation reformats gathered data into validated
   `AgentResponse` JSON (two-pass structured output).
4. 180s wall-clock timeout enforced via `ThreadPoolExecutor`.

## Consequences

- **Positive**: lower latency and token consumption than multi-agent supervision;
  simpler state management; one place to validate response structure
  (`_validate_response`); easy to reason about and debug.
- **Negative**: a single failure in one tool call stalls the whole answer; no
  parallel tool fan-out or independent review of intermediate steps; long-running
  chains can hit the 180s timeout (observed once in the model benchmark, ADR-006).

## Alternatives considered

- **Multi-agent supervision** (planner + worker + reviewer): rejected — supervision
  overhead, state-management complexity, excessive token consumption, and higher
  latency with no clear benefit for this scope (APPROACH.md §5).
- **Single-shot LLM call with all context preloaded**: rejected — cannot handle
  iterative retrieval or multi-step queries reliably; the tool loop exists for this.
