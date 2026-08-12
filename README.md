# SSI Sales Intelligence Agent

An API that answers sales questions over structured sales data and supporting notes. It handles factual (`WHAT`), causal (`WHY`), and recommendation (`WHAT_TO_DO`) questions, returning citations, confidence, and a response status.

## Features

- SQL-backed analysis of sales, targets, promotions, stockouts, products, territories, reps, and distributors
- Semantic search over cleaned business notes
- Structured responses with citations and confidence scores
- Optional Redis semantic caching
- Direct execution through FastAPI or asynchronous processing through QStash

## Requirements

- Python 3.11+
- A Gemini API key for embeddings
- An OpenAI-compatible model endpoint for the agent
- PostgreSQL, Redis, ChromaDB Cloud, and QStash for the hosted setup

SQLite, local ChromaDB, and direct requests can be used for local development where supported.

## Setup

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

The API is available at `http://127.0.0.1:8000`. FastAPI documentation is available at `/docs`.

## API

### Authentication

All endpoints except `/webhook/process` require an API key when `API_AUTH_TOKEN` is set in `.env`:

```bash
curl -X POST http://your-host/ask-direct \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-token' \
  -d '{"question":"Why did SparkClean 1kg sales spike in Mumbai?"}'
```

Leave `API_AUTH_TOKEN` empty for local development — auth is disabled and no header is required.

`/webhook/process` is exempt from the API key: it authenticates via the QStash `Upstash-Signature` header instead.

### Direct request

Use `/ask-direct` for local or synchronous execution:

```bash
curl -X POST http://127.0.0.1:8000/ask-direct \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did SparkClean 1kg sales spike in Mumbai?"}'
```

### Queued request

Use `/ask` when QStash and Redis are configured. The endpoint enqueues the question, waits for the webhook result, and caches successful responses.

QStash calls `/webhook/process`; configure the public webhook base URL and signing keys in `.env`.

### Cache invalidation

The semantic cache is TTL-based (600s default) and is also invalidated explicitly on data update events via `POST /cache/invalidate`, which clears all cached entries:

```bash
curl -X POST http://127.0.0.1:8000/cache/invalidate
```

Pre-synthesizing cached responses for frequent topics is future work.

**Auth:** `/cache/invalidate` requires `X-API-Key: <token>` when `API_AUTH_TOKEN` is set — see [Authentication](#authentication).

## Data

- `Data/` contains the source tables and data dictionary.
- `cleaned/` contains normalized tables used by the application.
- `omitted/` contains rows excluded during cleaning.
- `working_prompts/` contains the prompts used during development.

The data model is a sales star schema with product, geography, rep, and distributor dimensions plus sales, targets, promotions, and stockout facts. See [`Data/DATA_DICTIONARY.md`](Data/DATA_DICTIONARY.md) and [`db.sql`](db.sql).

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
```
