# SSI — Sales Intelligence Agent

Ask sales questions in plain English; get SQL-backed answers with citations, confidence scores, and a response status. The agent handles factual (`WHAT`), causal (`WHY`), and recommendation (`WHAT_TO_DO`) questions over a star-schema sales dataset and cleaned business notes — either synchronously or through an async queue.

## Highlights

- **SQL-backed analysis** over sales, targets, promotions, stockouts, products, territories, reps, and distributors
- **LangGraph single-agent tool loop**: classifies the question, then composes SQL or vector search as needed, and generates a cited answer
- **Semantic caching** (Redis, cosine similarity ≥ 0.97, TTL): repeat questions are served without another model call
- **Async by default**: `/ask` enqueues via QStash; a signature-verified webhook drives processing. `/ask-direct` is available for synchronous use
- **Structured responses**: answer, citations, confidence, and status in one JSON payload
- **Golden-set evals** with an offline fake mode — CI-friendly, no live model required
- **Clean data pipeline**: raw tables → cleaned star schema → omitted-row audit trail (see `Data/`, `cleaned/`, `omitted/`)

## Architecture

```
            ┌────────────────────────────── async path ──────────────────────────────┐
POST /ask ──▶ QStash queue ──▶ POST /webhook/process (Upstash-Signature verified) ──┤
                                                                                     ▼
POST /ask-direct ────────────────────────────────────────────────────────────▶ LangGraph agent
                                                                                     │
                                             classify → SQL (SQLAlchemy star schema) │
                                             or semantic search (ChromaDB + Gemini)   │
                                                                                     ▼
                                         answer + citations + confidence ──▶ Redis semantic cache
                                                                                     │
                                                     Langfuse tracing (optional) ◀────┘
```

Key decisions (agent loop over multi-agent, QStash over a local task queue, cache threshold/TTL, PII redaction, model choice) are recorded in [`docs/adr/`](docs/adr/) as ADR-001…006. A technical deep-dive lives in [`APPROACH.md`](APPROACH.md).

## Tech stack

| Layer | Tech | Role |
|---|---|---|
| API | FastAPI | HTTP endpoints, auth, request handling |
| Agent | LangGraph | Single-agent tool loop (classify → query → answer) |
| Agent model | `deepseek-v4-flash` via OpenAI-compatible endpoint | Response generation |
| Retrieval | ChromaDB + Gemini embeddings (1536-dim) | Semantic search over business notes |
| Data layer | SQLAlchemy star schema | SQLite locally, PostgreSQL in production |
| Cache | Redis semantic cache (cosine ≥ 0.97, TTL 600s) | Serve repeat questions without a model call |
| Queue | QStash + Upstash Redis | Async processing with signed webhooks |
| Observability | Langfuse (optional) | Trace agent runs |
| Evals | Golden question set + policy runner | `tests/evals/`, fake or live mode |

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set the values needed for the integrations you plan to use in `.env`. Do not commit `.env` or credentials.

Start the API:

```bash
uvicorn src.api.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive docs at `/docs`.

## API reference

**Authentication:** all endpoints except `/webhook/process` require `X-API-Key` when `API_AUTH_TOKEN` is set in `.env`. Leave it empty for local development — auth is disabled. `/webhook/process` is exempt: it authenticates via the QStash `Upstash-Signature` header.

| Endpoint | Mode | Description |
|---|---|---|
| `POST /ask` | Async | Enqueues the question on QStash, waits for the webhook result, caches successful responses |
| `POST /ask-direct` | Sync | Runs the agent inline — use for local or synchronous execution |
| `POST /webhook/process` | Async | Consumes the queue (QStash signature verified) |
| `POST /cache/invalidate` | Sync | Clears all semantic-cache entries (TTL-based otherwise, 600s default) |

Example:

```bash
curl -X POST http://127.0.0.1:8000/ask-direct \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did SparkClean 1kg sales spike in Mumbai?"}'
```

## Docs

- [`APPROACH.md`](APPROACH.md) — technical deep-dive: architecture, design rationale, limitations
- [`ARTEFACT.md`](ARTEFACT.md) — data reconciliation: what was cleaned, what was omitted, and why
- [`docs/adr/`](docs/adr/) — ADR-001…006 with index
- [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md) — data-quality audit
- [`docs/LESSONS_LEARNED.md`](docs/LESSONS_LEARNED.md) — engineering takeaways
- [`docs/MODEL_BENCHMARK.md`](docs/MODEL_BENCHMARK.md) — agent-model benchmark and selection
- [`Data/DATA_DICTIONARY.md`](Data/DATA_DICTIONARY.md) — star-schema dictionary
- [`db.sql`](db.sql) — schema definition

## Tests

```bash
python -m unittest discover -s tests
```

Agent evals (golden question set + policy checks): `python tests/evals/run_evals.py --fake` runs offline against a scripted stub; omit `--fake` to run against the live agent.

## Project layout

```text
src/api/          FastAPI routes
src/agent/        Agent graph, tools, prompts, and response models
src/cache/        Semantic cache and embeddings
src/internal/db/  Database models, sessions, and vector search
scripts/          Data cleaning, preprocessing, and embedding utilities
tests/            API, cache, and data-cleaning tests
tests/evals/      Golden-set agent evals and runner
Data/             Raw source tables
cleaned/          Normalized tables used by the application
omitted/          Rows excluded during cleaning
```

*Note: originally built as a university data-analytics assignment over a sample FMCG sales dataset; reworked and maintained here as a portfolio project.*
