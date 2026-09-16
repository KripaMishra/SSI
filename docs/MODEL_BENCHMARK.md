# Model Benchmark — agent LLM choice (#6)

**Date:** 2026-08-12
**Harness:** `tests/evals/run_evals.py` (live mode) — 14-question golden set, per-question
policy checks (intent, status, WHY citations, confidence) + `src/agent/graph.py`
response validation.
**Endpoint:** `https://opencode.ai/zen/go/v1` (key in `.env`).
**Effective model knob:** `MODEL_NAME` env var (pydantic-settings field `model_name`;
default `deepseek-v4-flash` hardcoded in `src/agent/config.py`). Note: `.env.example`
previously documented `AGENT_MODEL`, which is **not** consumed — fixed to `MODEL_NAME`
in the same change.

## Results

| Model | Pass rate | WHAT | WHY | WHAT_TO_DO | OOD | Wall time (14 q) | Per-q median / avg |
|---|---|---|---|---|---|---|---|
| `deepseek-v4-flash` (default) | **13/14 (93%)** | 5/5 | 4/4 | 2/3 | 2/2 | **~9.9 min** | ~36s / ~46s |
| `kimi-k2.6` (fast-tier candidate) | 12/14 (86%) | 5/5 | 3/4 | 2/3 | 2/2 | ~16.4 min | ~45s / ~70s |

## Failures

- `whattodo-1-restock-glucojoy` — **both models**: agent produced intent
  `WHAT_TO_DO` with a non-`PENDING_APPROVAL` status; rejected by
  `graph._validate_response` (`ResponseValidationError`). Shared prompt/spec-level
  behavior, not model-specific.
- `why-3-promo-delhi` — **kimi-k2.6 only**: `AgentTimeoutError` (no response within the
  agent's 180s per-question timeout; question took ~6 min wall incl. retries). No
  timeouts with `deepseek-v4-flash`.

## Decision

**Keep `deepseek-v4-flash` as the default.** The fast-tier candidate `kimi-k2.6` is
both *slower* (16.4 vs 9.9 min; 66% slower wall time) and *less accurate* (86% vs 93%),
and it breached the 180s response timeout on one question. The original assumption in
APPROACH.md limitation #4 ("deepseek-v4-flash is overkill and slower than needed") is
refuted by this data for the current catalog. Revisit if a fast-tier model beats flash
on **both** axes (pass rate ≥ and wall time <) in a future benchmark.

## Reproduce

```bash
MODEL_NAME=deepseek-v4-flash .venv/bin/python tests/evals/run_evals.py   # baseline
MODEL_NAME=kimi-k2.6     .venv/bin/python tests/evals/run_evals.py   # candidate
```

Raw logs: `MODEL_NAME`-tagged runs under `~/.pi` session workspace (not committed).
