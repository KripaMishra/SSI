# Sales Intelligence Agent

Ask sales questions in plain English; get SQL-backed answers with citations, confidence scores, and a response status. The agent handles factual (`WHAT`), causal (`WHY`), and recommendation (`WHAT_TO_DO`) questions over a star-schema sales dataset and cleaned business notes — either synchronously or through an async queue.

## Highlights

- **SQL-backed analysis** over sales, targets, promotions, stockouts, products, territories, reps, and distributors
- **LangGraph single-agent tool loop**: classifies the question, then composes SQL or vector search as needed, and generates a cited answer
- **Semantic caching** (Redis, cosine similarity ≥ 0.97, TTL): repeat questions are served without another model call
- **Async by default**: `/ask` queues one Dramatiq task and returns its `task_id`; poll `GET /tasks/{task_id}` for the result. `/ask-direct` is available for synchronous use
- **Structured responses**: answer, citations, confidence, and status in one JSON payload
- **Golden-set evals** with an offline fake mode — CI-friendly, no live model required
- **Clean data pipeline**: raw tables → cleaned star schema → omitted-row audit trail (see `Data/`, `cleaned/`, `omitted/`)

## Architecture

```
POST /ask ──▶ Dramatiq (Redis, queue: asks) ──▶ worker process ──▶ LangGraph agent
   │            one task per API call            dramatiq             │
   ▼                                            -Q asks -t 8          │
202 {"task_id", "status": "QUEUED"}                 classify → SQL (SQLAlchemy star schema)
GET /tasks/{task_id} ──▶ QUEUED | RUNNING |              or semantic search (ChromaDB + Gemini)
                         SUCCESS(response) |                              │
                         FAILURE(error)      answer + citations + confidence
                                                                          ▼
POST /ask-direct ──▶ same pipeline, inline (sync) ──▶ Redis semantic cache ──▶ Langfuse (optional)
```

Key decisions (agent loop over multi-agent, QStash over a local task queue, cache threshold/TTL, PII redaction, model choice) are recorded in [`docs/adr/`](docs/adr/) as ADR-001…007. ADR-007 describes the Dramatiq task queue this branch uses in place of ADR-003's QStash; the two are alternative implementations of the same service. A technical deep-dive lives in [`APPROACH.md`](APPROACH.md).

## Tech stack

| Layer | Tech | Role |
|---|---|---|
| API | FastAPI | HTTP endpoints, auth, request handling |
| Agent | LangGraph | Single-agent tool loop (classify → query → answer) |
| Agent model | `deepseek/deepseek-v4-flash` via the Command Code Provider API | Response generation |
| Retrieval | ChromaDB + Gemini embeddings (1536-dim) | Semantic search over business notes |
| Data layer | SQLAlchemy star schema | SQLite locally, PostgreSQL in production |
| Cache | Redis semantic cache (cosine ≥ 0.97, TTL 600s) | Serve repeat questions without a model call |
| Queue | Dramatiq on Redis (queue `asks`) | One worker process per API call type; task records + status in Redis |
| Observability | Langfuse (optional) | Trace agent runs |
| Evals | Golden question set + policy runner | `tests/evals/`, fake or live mode |

## Quickstart

```bash
uv sync            # installs dependencies from pyproject.toml + uv.lock
cp .env.example .env
```

Set the values needed for the integrations you plan to use in `.env`. Do not commit `.env` or credentials.

Agent inference runs on the [Command Code Provider API](https://commandcode.ai/docs/provider)
(OpenAI-compatible): create a key in Studio → API keys and set it as `OPENAI_API_KEY` in `.env`,
with `OPENAI_BASE_URL=https://api.commandcode.ai/provider/v1` and a namespaced `MODEL_NAME`
(default `deepseek/deepseek-v4-flash`). Every plan except Go includes API access; usage meters
against the plan's credits. See [ADR-008](docs/adr/008-command-code-provider-api.md).

Run the whole stack (API + worker + Redis) with Docker Compose:

```bash
make up            # docker compose up --build
```

Or run the pieces yourself — the API needs a worker alongside it, otherwise queued tasks stay
`QUEUED`:

```bash
make api-dev       # API on 127.0.0.1:8000, reloads on changes
make worker        # one worker for the "asks" queue
```

`make help` lists every command.

The API is available at `http://127.0.0.1:8000`; interactive docs at `/docs`.

## API reference

**Authentication:** all endpoints require `X-API-Key` when `API_AUTH_TOKEN` is set in `.env`. Leave it empty for local development — auth is disabled.

| Endpoint | Mode | Description |
|---|---|---|
| `POST /ask` | Async | Cache hit answers inline; a miss queues one Dramatiq task and returns `202` with its `task_id` |
| `GET /tasks/{task_id}` | Sync | Task status: `QUEUED`, `RUNNING`, `SUCCESS` (with `result`) or `FAILURE` (with `error`) |
| `POST /ask-direct` | Sync | Runs the agent inline — use for local or synchronous execution |
| `POST /cache/invalidate` | Sync | Clears all semantic-cache entries (TTL-based otherwise, 600s default) |

Example:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did SparkClean 1kg sales spike in Mumbai?"}'
# {"task_id":"8cdcae57-…","status":"QUEUED"}

curl http://127.0.0.1:8000/tasks/8cdcae57-…
# {"status":"SUCCESS","result":{"response":{"answer":"…","citations":[…],…}},…}
```

## Docs

- [`APPROACH.md`](APPROACH.md) — technical deep-dive: architecture, design rationale, limitations
- [`ARTEFACT.md`](ARTEFACT.md) — data reconciliation: what was cleaned, what was omitted, and why
- [`docs/adr/`](docs/adr/) — ADR-001…007 with index
- [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md) — data-quality audit
- [`docs/LESSONS_LEARNED.md`](docs/LESSONS_LEARNED.md) — engineering takeaways
- [`docs/MODEL_BENCHMARK.md`](docs/MODEL_BENCHMARK.md) — agent-model benchmark and selection
- [`Data/DATA_DICTIONARY.md`](Data/DATA_DICTIONARY.md) — star-schema dictionary
- [`db.sql`](db.sql) — schema definition

## Tests

```bash
make test          # python -m unittest discover -s tests
```

Agent evals (golden question set + policy checks): `python tests/evals/run_evals.py --fake` runs offline against a scripted stub; omit `--fake` to run against the live agent.

## Project layout

```text
src/api/          FastAPI routes
src/agent/        Agent graph, tools, prompts, and response models
src/cache/        Semantic cache and embeddings
src/queue/        Dramatiq broker, task actors, task records
src/internal/db/  Database models, sessions, and vector search
scripts/          Data cleaning, preprocessing, and embedding utilities
tests/            API, cache, and data-cleaning tests
tests/evals/      Golden-set agent evals and runner
Data/             Raw source tables
cleaned/          Normalized tables used by the application
omitted/          Rows excluded during cleaning
```

*Note: originally built as a university data-analytics assignment over a sample FMCG sales dataset; reworked and maintained here as a portfolio project.*
