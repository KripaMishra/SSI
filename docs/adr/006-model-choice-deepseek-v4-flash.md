# ADR-006: Model choice — `deepseek-v4-flash` as default

## Status

Accepted (benchmarked 2026-08-12; see `docs/MODEL_BENCHMARK.md`).

## Context

APPROACH.md limitation #4 originally assumed `deepseek-v4-flash` was "overkill and
slower than needed" for the fast-tier candidate. The model is the agent's core
loop (ADR-001) and its single largest latency/cost driver. Before changing the
default, the team ran a live benchmark against the fast-tier candidate
`kimi-k2.6`.

## Decision

**Keep `deepseek-v4-flash` as the default model.**

Benchmark (`tests/evals/run_evals.py`, 14-question golden set, live mode,
per-question policy checks + `graph._validate_response`):

| Model | Pass rate | Wall time (14 q) | Notes |
|---|---|---|---|
| `deepseek-v4-flash` | **13/14 (93%)** | **~9.9 min** | no timeouts |
| `kimi-k2.6` | 12/14 (86%) | ~16.4 min | 180s `AgentTimeoutError` on `why-3-promo-delhi` |

The candidate is both slower (66%) and less accurate, and breached the 180s
timeout. The default is configurable via the `MODEL_NAME` env var (pydantic-settings
`model_name` in `src/agent/config.py`).

## Consequences

- **Positive**: highest measured pass rate at lowest wall time; no response
  timeouts; the benchmark refuted the "overkill" assumption with data.
- **Negative**: one shared failure remains (`whattodo-1-restock-glucojoy` —
  non-`PENDING_APPROVAL` status) — a prompt/spec-level issue, not model-specific;
  the default must be re-benchmarked if a fast-tier model appears that beats flash
  on both pass rate and wall time.

## Alternatives considered

- **`kimi-k2.6`** (fast-tier candidate): rejected by the benchmark — slower and
  less accurate, with a timeout.
- **Sticking with the unverified "flash is overkill" assumption**: rejected — the
  benchmark showed switching would regress both axes.
