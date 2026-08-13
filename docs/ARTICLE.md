# Sales Intelligence Agent

*I asked an AI to build a sales-intelligence agent over a messy sample dataset. Then I audited the data, benchmarked the model with the agent it built, and wrote down everything that went wrong. Here's the whole story — the working parts, the embarrassing parts, and the numbers to back both.*

---

## TL;DR

- **What:** an agent that answers sales questions in plain English — "Why did SparkClean 1kg spike in Mumbai in September?" — with SQL-backed answers, citations to source data, a confidence score, and an explicit response status.
- **Input:** 8 CSV tables (52 weeks, 5 categories, 12 territories) plus 30 unstructured text documents (emails, notes, circulars).
- **Stack:** FastAPI + LangGraph (single-agent tool loop), a managed queue for async requests, a semantic cache for repeat questions, and a golden-set eval harness. ~98 tests.
- **Origin:** a university data-analytics assignment over a sample FMCG dataset, reworked as a portfolio project. The repo is public: [github.com/KripaMishra/SSI](https://github.com/KripaMishra/SSI).

If you only read one section, read **"The data was the real project"** and **"What went wrong"**. The rest is the good news.

---

## What it does, in one example

You type:

```
Why did SparkClean 1kg sales spike in Mumbai in Sep 2025?
```

The agent:

1. Classifies the question as a **WHY** (causal) question.
2. Decides what it needs — a database query, a search through business notes, or both.
3. Runs the tools, gathers evidence, and writes an answer.
4. Returns structured JSON: the answer, **citations** (mandatory for WHY questions), a confidence score, and a status.

Three question types, three contracts:

| Type | Meaning | Guarantee |
|---|---|---|
| **WHAT** | "What were GlucoJoy's monthly sales vs target in North in Nov 2025?" | Factual answer from the database |
| **WHY** | "Why did sales spike in Mumbai?" | Causal analysis **with citations** — no citations, no answer |
| **WHAT_TO_DO** | "Which SKUs should we restock?" | A recommendation, returned with `PENDING_APPROVAL` — the agent can suggest, it cannot decide |

That last contract is the one I'm proudest of. The agent is explicitly not allowed to give recommendations as fact. It proposes; a human approves. It's a one-line policy check in code, and it turns "an AI that talks to your database" into "an AI that respects its own limits."

---

## The data was the real project

The dataset is a sample FMCG sales export. Sample datasets are supposed to be tidy. This one was not.

**Four date formats. In the same column.** `YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YY`, and `DD Mon YYYY` — 10,972 rows affected. Excel was involved, and Excel does not apologize.

Then the sales values arrived as strings: `"Rs 1,234"`. 9,416 rows. Someone formatted currency into a numeric column, which is the data-entry equivalent of writing a memo in Comic Sans.

And then there was **9999**. The number 9999 is not a sales figure. It is a sentinel — a placeholder meaning "we don't know" — and it appeared 771 times in the units column. A further 734 rows had negative units (probably returns, possibly errors; the dataset has no returns dimension, so we treated them as errors). One row had -9999, which is 9999's sadder cousin.

The full cleaning ledger, for the record:

| Problem | Rows | Fix |
|---|---|---|
| 4 date formats | 10,972 | Normalized to one format |
| `"Rs 1,234"` string values | 9,416 | Extracted the number |
| 9999 sentinel | 771 | → NULL, flagged |
| Negative units | 734 | → NULL, flagged |
| -9999 sentinel | 1 | → NULL, flagged |
| Duplicate rows | 23 pairs | Kept first, rest → `omitted/` |
| PII in business notes | 12 (4 names, 4 emails, 4 phones) | Redacted to `<REDACTED_*>` |

### Don't delete — annotate

The design decision I'd defend in a meeting: **nulled rows are not deleted.** Every bad unit value is replaced with NULL *and* tagged with a flag (`sentinel_9999`, `negative`, `ok`). The agent is told: flagged rows are unreliable — don't use them in conclusions, and say so when you quote affected data.

Why not just delete? Because deleted data can't be audited. The reconciliation report totals **38,630,596 units** across 52 weeks, computed from exactly the 60,426 rows flagged `ok` — and you can re-check that number any time, because the flagged rows still exist, annotated. Deleting is a one-way door; flagging keeps the audit trail open.

### The bombshell the audit found

The data-quality audit (which was itself a GitHub issue, closed with evidence) surfaced something the cleaning pass missed:

**The `value` column is synthetic.** For 53,849 of 58,262 valid rows, `value = 0.75 × MRP × units` — exactly, to the decimal. A further 4,385 rows match within one rupee of rounding. Total: **~99.95% of the dataset's value column is a flat 25% discount applied by whoever generated the sample, not a measurement.**

This is not an error — it's a property of the data. But it caps what the agent can honestly conclude: any question about "realized prices" or "margins" will find the same constant, because there's nothing else there to find. The audit documented it precisely so nobody (including the agent) over-reads the number. There are also 15 rows where value implies ~24× the recorded units — consistent with a case being 24 packs — which remains unexplained, because the dataset doesn't say.

A sample dataset that quietly fakes its own numbers is the most valuable lesson the project taught me: **when your data looks too clean, someone cleaned it for you — and they may not have told you how.**

---

## How it's built (the parts you'd care about)

Four moving pieces, each with a boring-sounding name and a fun reason to exist:

### 1. The agent: one brain, three tools

The agent is a single LLM in a loop (LangGraph): classify the question → call tools → write the answer → validate. Three tools:

- `query_database` — a query builder over the star schema (the "hub-and-spoke" table layout) for structured data.
- `search_docs` — vector search over the 30 business notes. Text is turned into coordinates (embeddings) so that similar *meaning* lands nearby, not just similar words.
- `describe_database` — lets the model inspect the schema itself instead of memorizing it.

We deliberately chose **one agent with tools** over a multi-agent committee. Multi-agent architectures sound impressive and cost tokens; a single agent with a tool loop does the same job with less latency, less state, and fewer moving parts. There's an ADR recording that decision (and five more like it).

The loop has a hard 180-second timeout, and output goes through two passes: the model gathers data freely, then a second call reformats it into a validated JSON contract. Validation is where the three question-type guarantees above are enforced — in code, not in vibes.

### 2. The queue: async by default

`POST /ask` doesn't run the agent inline. It drops the question into **QStash** (a managed queue), which calls a webhook (`/webhook/process`) when it's ready — with a signed signature so only the queue can trigger processing. The client polls for the result.

Why bother? Because Vercel serverless functions (the deployment target) are short-lived: code runs in bursts on rented machines, and there's no always-on server — which means no always-on worker process. A managed queue is the serverless-native way to do async work. More on this in the next section, because it nearly cost me the project.

### 3. The cache: don't pay for the same answer twice

Repeat questions are the norm in sales analytics, so the API caches responses **semantically**: if a new question is 97% similar (cosine ≥ 0.97) to a cached one, you get the stored answer without another model call. TTL of 10 minutes, hot-cache promotion on hits, and an explicit invalidation endpoint for data updates.

It's the difference between a demo that costs pennies and a demo that costs dollars. And the 0.97 threshold was chosen deliberately — tight enough that a genuinely different question still gets a fresh answer.

### 4. The evals: a golden set with teeth

The most important piece for trust: **14 golden questions** (5 WHAT, 4 WHY, 3 WHAT_TO_DO, 2 out-of-scope), each with policy checks — did it return the right intent? The right status? Citations on WHY questions? A confidence score?

This is what let us *measure* the model choice instead of vibes-ing it (next section). It runs offline against a stub for CI, or live against a real model.

---

## What went wrong (the honest part)

The repo documents its failures in detail — `docs/LESSONS_LEARNED.md` — and the failures are the most credible part of the project. Here's the short version.

### The plan met reality at 16:07, and the plan lost

The original plan (a `task_plan.md`): Redis cache + **python-rq** queue + Docker Compose with a worker service. Reasonable plan. Committed to. Gitignored later.

The problem: the plan never considered the deployment target. The target was **Vercel serverless** — where a long-running RQ worker literally cannot run. The constraint surfaced the moment queue work started:

- **16:07** — queue dependencies landed (with the first QStash commit, not RQ — the `rq` dependency never existed).
- **16:08** — the swap instruction landed: *"swap the redis with upstash instance of redis; swap the rq with QStash."*
- **16:46** — QStash implementation done: webhook endpoint, signature verification, signing-key fix.

The plan was dead within two minutes of the work starting. Nothing about the RQ path was ever built — no worker, no compose file. But the cost was real: plan churn, prompt churn, and **burned AI credits that were supposed to fund review** (see: the AI-tooling constraints below).

The lesson is embarrassingly simple and I'll state it plainly: **lock your infrastructure and your deploy target before you write code.** A plan that gets gitignored mid-execution is a plan that's already stale. This is recommendation #1 in the lessons doc, and it cost the most to learn.

### The AI-tooling constraints (a confession)

The project was built with an AI agent, under constraints that are worth being honest about:

- **Retry churn.** The model repeatedly failed at things like putting citations in the wrong field, hardcoding confidence, or bypassing the query layer we built — six-plus defects found *one at a time*. Each retry is a full task re-run; the effective cost multiplier was ~2–3× the ideal.
- **Text-only model.** No image input. Debugging HTML rendering issues meant guess-and-retry instead of *looking at the page*. Screenshots beat prayer.
- **Token budget.** The queue rework + retries blew through the allocation, and the cheapest-to-fix findings (deploy constraint, review gap) landed as documentation debt instead of being prevented.

None of this is an excuse — it's a measurement. AI-driven development is not free, and its failure modes are *process* failure modes: plan against them.

### The review loop that got cut

The queue pivot displaced the review activities — evals, benchmark, docs — which all ended up as follow-up work on Aug 6–12 instead of part of the build. That gap is exactly where the deploy-constraint bug slipped through. Every subsequent task in the showcase pass ran with a mandatory reviewer pass: worker subagent → reviewer → close with commit references. **Reviewers caught real defects in 4 of 9 tasks** (including a non-ASCII API key crashing the auth compare — a bytes-vs-string bug that would have shipped). Review loops work. Budget them from day one.

---

## What we measured (the turn-around)

### The benchmark

The original assumption in the design doc: the default model (`deepseek-v4-flash`) was "overkill and slower than needed" — a fast-tier model should do. The benchmark set out to prove that. It proved the opposite:

| Model | Pass rate | Wall time (14 questions) |
|---|---|---|
| `deepseek-v4-flash` (default) | **13/14 (93%)** | **~9.9 min** |
| `kimi-k2.6` (fast-tier candidate) | 12/14 (86%) | ~16.4 min |

The "fast" candidate was 66% *slower* and *less* accurate, and it breached the 180-second agent timeout on one question. The default stayed. The assumption was refuted with data — which is the entire point of having a golden set.

Two findings made this benchmark worth it beyond the table:

1. **Both models failed the same question** — a WHAT_TO_DO question where the agent returned a non-`PENDING_APPROVAL` status. Same failure on both models means it's a *spec-level* bug in the prompt, not a model deficiency. That's the difference between debugging your code and swapping models hoping.
2. **The benchmark found a doc bug.** `.env.example` documented an env var (`AGENT_MODEL`) that the config code never actually read (the real one was `MODEL_NAME`). Found because we had to set the model to run the benchmark. Documentation that lies is a bug, and measurement finds it.

### The hardening pass

After the measurements, the follow-up work (the review loop, arriving fashionably late):

- Data-quality anomalies catalogued with repro steps — 10 newly surfaced classes, several flagged as *not addressed*, because honest documentation includes what you chose not to fix.
- **Six ADRs** — one-page records of every significant decision (single agent, star schema, QStash, caching, PII redaction, model choice) with alternatives considered. The article-writing practice worth copying: a decision without its reasoning is a future regret.
- API secured: `X-API-Key` auth with constant-time comparison, webhook exempt (it has its own signature check).
- Tests consolidated and expanded: **70 → 98 passing**.
- The project's own benchmark result was applied to the project's own process: every subagent in the showcase pass was pinned to `deepseek-v4-flash` — the benchmark winner. The agent built the benchmark, the benchmark picked the model, the model built the rest. I find this loop deeply satisfying.

---

## Things worth stealing

1. **Lock infra + deploy target before coding.** A gitignored plan is a stale plan.
2. **Budget a dedicated review loop** — and don't let rework eat it.
3. **Don't delete data, annotate it.** NULL + flag beats DELETE, because the audit trail survives.
4. **Eval with a golden set and policy checks** — the same test that caught both a model timeout and a spec-level bug.
5. **ADRs for AI-made decisions.** When the builder is a stochastic parrot, write the reasoning down while it's still cheap.
6. **Cap retries and log them.** State what changed, cap at 2, then change strategy. Token waste should be visible and auditable.
7. **Assume 2–3× the token budget you think you need.** The ideal path (no retries, no rework) is not the realistic one.
8. **Benchmark before you trust a label.** "Fast tier" was neither. The default was right, and now there's a number saying so.

---

## The reading map

Everything is in the repo, public, commit-verified:

- `README.md` — the front door (architecture diagram, API reference, quickstart)
- `APPROACH.md` — the technical deep-dive and the honest limitations list
- `ARTEFACT.md` — the reconciliation report (38,630,596 units and how)
- `docs/DATA_QUALITY.md` — the anomaly catalogue, including the synthetic-value finding
- `docs/LESSONS_LEARNED.md` — the process post-mortem with commit evidence
- `docs/MODEL_BENCHMARK.md` — the benchmark, reproducible
- `docs/adr/` — six decision records
- `tests/evals/` — the golden set and the eval runner

*A note on honesty: this project began as a university assignment over a sample dataset. The sample lied a little (that synthetic value column), the process stumbled (that queue pivot), and the measurements fixed more than the code did. I've kept all of it — the failures included — because a portfolio that only shows the wins is just marketing, and marketing doesn't teach anyone anything.*
