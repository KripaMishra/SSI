# Handoff: Write the Public Process Article for SSI

**Status:** Ready for a writing agent.
**Purpose:** This document is a complete tracing + handoff package. A writing
agent should read it, then read the referenced files **in the repo** for full
text, and produce a public article documenting the whole process: how SSI was
built, what went wrong, what was measured, and what a reader can learn from it.

The article is intended to be posted publicly (blog / LinkedIn / dev.to). It
should be honest (the repo itself documents failures and trade-offs), factual
(every claim can be verified against the repo), and portfolio-grade.

---

## 0. How to use this document

1. Read this file end-to-end.
2. Read the files under **§2 (existing docs)** in the repo — they are the raw
   material. Section headings and key facts are summarized here so you can
   plan the article before reading everything.
3. Check **§10 (missing docs)** — write the missing pieces the article needs
   (or note them as follow-ups) before or while drafting.
4. Draft the article. Suggested target: `docs/ARTICLE.md` in the repo
   (markdown), then convert to the publishing platform's format. If the
   article is long, propose splitting it (e.g. engineering blog part 1:
   data+agent; part 2: infrastructure+process).
5. Verify against **§11 (fact-check checklist)** before declaring done.

**Working constraints (inherited from the project):**

- All work happens in the repo on branch `develop`. Micro-commits with
  conventional messages (`docs: ...`). Do NOT push without explicit approval.
- Do NOT invent numbers. Every statistic cited here has a source file; cite
  the file in the article (or verify the number against it yourself).
- Do NOT include secrets: `.env` values (QStash token, Gemini key, OpenAI key)
  must never appear. The dataset is synthetic/sample (see §3.1), and the
  benchmark used a real paid LLM endpoint — describe it without credentials.
- Article tone: honest engineering story, not marketing. The repo's docs
  (APPROACH.md limitations, LESSONS_LEARNED.md) are the truth source.

---

## 1. Repo facts (verified 2026-08-12)

| Fact | Value |
|---|---|
| Repo path | `/home/kripa/Personal/projects/SSI` |
| Remote | `https://github.com/KripaMishra/SSI` (public GitHub repo) |
| Working branch | `develop` (26 commits ahead of `main`; **not pushed**) |
| `main` tip | `06b343b` `doc: update readme` (last pre-showcase commit, exists on remote) |
| Showcase commit chain | `f841217` → `85131ba`, 26 micro-commits, all local |
| Test suite | `.venv/bin/python -m unittest discover -s tests` → **96 tests, OK** (~53 s) |
| Eval suite | `tests/evals/run_evals.py --fake` (offline) / live mode |
| Project origin | University data-analytics assignment over a sample FMCG sales dataset; reworked as portfolio project (one-line footnote in README) |

GitHub issues (all in milestone "Showcase & Personal Project"):

| # | Title | State | Delivered by |
|---|---|---|---|
| 1 | Langfuse tracing broken on Vercel | CLOSED (not planned) | — |
| 2 | Catalogue undocumented sales anomalies | CLOSED | `docs/DATA_QUALITY.md` (`f841217`, review `42e9538`) |
| 3 | Add agent evals suite | CLOSED | `tests/evals/` (`0d7446d`, `440f8ba`, `2f44d42`, `fdcdfd6`) |
| 4 | Data-event cache invalidation | CLOSED | `POST /cache/invalidate` (`123c8df`, `c9db073`, `951e32f`) |
| 5 | Raw SQL query support | CLOSED (removed, not planned) | — |
| 6 | Revisit agent model choice + benchmark | CLOSED | `docs/MODEL_BENCHMARK.md` (`38cf9e1`, `306cba9`) |
| 7 | Lessons learned doc | CLOSED | `docs/LESSONS_LEARNED.md` (`9aed24d`, review `4aff6e0`) |
| 8 | Consolidate duplicate test dirs | CLOSED | `6e1fe43`, `bca454a` |
| 9 | Showcase UI on Vercel | **OPEN** | (UI session; not started) |
| 10 | ADRs from APPROACH.md trade-offs | CLOSED | `docs/adr/` (`27bce24`, review `16c152a`) |
| 11 | Secure public API (auth/rate limiting) | CLOSED | `5abc7b3`, `8765bed`, `2c5a6a1`, `200834b` + review fixes `1ce866c`, `0ae5607`, `91d456e` |
| 12 | README rewrite for portfolio | CLOSED | `85131ba` |
| 13 | UI: design showcase interface | **OPEN** | (UI session; not started) |

---

## 2. Existing documentation (the article's raw material)

All paths are relative to repo root. Read them in the repo — the summaries
below are accurate as of 2026-08-12 but the files are the source of truth.

### 2.1 `README.md` (119 lines) — portfolio front door
Pitch ("Ask sales questions in plain English; get SQL-backed answers with
citations, confidence scores, and a response status"), 6 highlight bullets,
ASCII architecture diagram (sync + async paths), tech-stack table, quickstart,
API reference table (4 endpoints + auth semantics + curl example), docs index,
test commands, project layout, provenance footnote.
→ **Skeleton for the article's "what is it" section.**

### 2.2 `APPROACH.md` (223 lines) — technical deep-dive
The single most important doc for the article:
- **Problem summary:** assistant answering WHAT / WHY / WHAT_TO_DO over 8 CSV
  tables (52 weeks, 5 categories, 12 territories) + 30 unstructured text docs;
  causal analysis with mandatory citations; recommendations returned with
  `PENDING_APPROVAL` status.
- **§0 Data cleaning table:** 12 issue classes with row counts and fixes
  (e.g. 4 date formats / 10,972 rows; `"Rs 1,234"` non-numeric values /
  9,416 rows; 9999 sentinel / 771 rows; negatives / 734 rows; 23 duplicate
  pairs omitted; territory aliases BLR/BGL/Bombay; distributor ID leading
  zeros; SKU tier abbreviations; region abbreviations).
- **§1 Data modelling:** star schema ER diagram (4 dims + 2 facts +
  promotions/stockouts), SQLAlchemy.
- **§2 Sentinel & negative handling:** null-with-flag design
  (`sales_units_flag`: `sentinel_9999` / `sentinel_-9999` / `negative` / `ok`).
- **§3 Text cleaning:** PII redaction pipeline (4 phones, 4 emails, 4 names
  → `<REDACTED_*>`), chunking (1 chunk per doc), metadata extraction.
- **§4 Retrieval & tools:** `search_docs` (ChromaDB + Gemini embeddings
  1536-d), `describe_database`, `query_database` (ORM query builder).
- **§5 Agent architecture:** LangGraph single-agent tool loop diagram,
  180 s timeout via `ThreadPoolExecutor`, two-pass structured output,
  `_validate_response()` policy checks (WHY ⇒ citations mandatory;
  WHAT_TO_DO ⇒ PENDING_APPROVAL; tool errors ⇒ ERROR).
- **§6 Message queue:** QStash sequence diagram (enqueue → webhook →
  signature verify → agent → Redis result → poll → cache).
- **§7 Semantic caching:** Gemini embeddings, cosine ≥ 0.97, TTL 600 s,
  hot-cache promotion, `POST /cache/invalidate`.
- **§8 Tracing:** Langfuse at module load, silent fallback.
- **AI Tool Usage section:** OpenCode/Cadra + ctxMode notes.
- **Trade-offs & Limitations 1–9:** single vs multi-agent; undocumented
  anomalies; all-or-nothing cache invalidation; model choice (resolved by
  benchmark); ORM query-builder limits; no eval suite (resolved); Langfuse
  broken on Vercel (issue #1, closed not planned); QStash migration burned
  AI credits and prevented review loops; AI-tooling constraints (retry
  prompts, text-only model, token policy).

### 2.3 `ARTEFACT.md` (58 lines) — reconciliation report
- National 52-week primary sales total: **38,630,596 units** (60,426 of
  61,932 rows with `sales_units_flag = "ok"`; 1,506 nulled/flagged rows
  excluded).
- Top-3 data-quality fixes by rows affected (dates 10,972; non-numeric
  values 9,416; sentinel/negative nullification 1,506).
- **Returns/unit-mixing rule:** negatives treated as data-quality issues, not
  returns (no returns dimension exists); flagged not deleted.
- Records excluded: 23 duplicate rows → `omitted/`; 1 promo row with
  territory="North" (FK violation) → `omitted/`; 12 PII redactions.
- Assumptions list (52-week window 2025-07-01 → 2026-06-23, etc.).

### 2.4 `docs/DATA_QUALITY.md` (338 lines) — anomaly catalogue
Part A: 8 documented+fixed classes (verified counts). Part B: 10 newly
surfaced classes, several NOT addressed: `dim_sku` duplicated master rows;
**value/units inconsistency (15–16 rows)**; **synthetic value construction
(value ≈ 0.75 × MRP × units for 54,853/59,348 rows — the dataset is
partially synthetic)**, outlier weeks (Oct 2025 festival block); right-skewed
units; target/sales calibration (ratio ≈ 0.95–0.99, corr ≈ 0.995); absent
SKU×territory combos (~74 % grid coverage); sparse support tables
(promotions 2 rows / stockouts 2 rows); diffuse missing units; plus a
checked-and-clean class. Includes repro steps and method/verification notes.
→ **This doc is the "data quality in the real world" story. The synthetic
value finding is article-worthy: it proves the audit found that ~92 % of the
dataset was generated, not collected.**

### 2.5 `docs/LESSONS_LEARNED.md` (155 lines) — the process post-mortem
The emotional core of the article. Contents:
- **Timeline with commit evidence** (one marathon session 2026-08-05):
  Phase 0 bootstrap (Jul 2–Aug 3); Phase 1 core agent (Aug 5, 02:00–04:00,
  ~15 small commits `b2af573`→`1158f25` — "went well: small steps");
  Phase 2 queue+cache per plan (`task_plan.md`: Redis + python-rq + Docker
  Compose, concurrency 5, TTL 10 min, 0.97 threshold) — first queue commit
  was already QStash (`ed140a1`, `30cfd66`); Phase 3 **mid-development
  RQ→QStash pivot** (16:07–16:46): swap prompt `7aa1e22` landed ~2 min
  after deps `6e02ad7`; Vercel entrypoint `ff8ccf4`; unused deps dropped
  `75ee659`; signing-key fix `df06007`; Phase 4 fixes+docs (18:00–19:30,
  incl. `1c3133b` first AI-constraints doc); Phase 5 follow-up (Aug 6–12:
  README `06b343b`, evals, benchmark, cache invalidation).
- **Cost analysis:** RQ existed only as a plan (no `rq` dep, no worker, no
  compose file ever landed); the real cost was plan/prompt churn + burned
  AI credits + dropped review loops (limitation #8), not a reimplementation.
- **AI-tooling constraint table:** retry prompts (retry factor ~2–3×,
  agent.md Bugs list shows 6+ defects found one at a time), text-only model
  (no image input for HTML debugging — guess-and-retry), token/request
  policy (unplanned expenditure), missing resource availability.
- **7 process recommendations:** (1) lock queue infra + deploy target before
  coding — a gitignored task plan is a stale-plan warning sign; (2) budget a
  dedicated review loop; (3) image-capable model for UI debugging; (4)
  prompt-retry discipline (state what changed, cap retries at 2, log prompts);
  (5) cost the swap before swapping; (6) pre-flight constraints into the repo
  not the prompt (`.env` prohibition → README/.env.example, e.g. `306cba9`);
  (7) provision 2–3× token budget for retries.

### 2.6 `docs/MODEL_BENCHMARK.md` (46 lines) — the measurement story
- Date 2026-08-12; harness `tests/evals/run_evals.py` live mode, 14-question
  golden set with per-question policy checks + graph response validation;
  endpoint `https://opencode.ai/zen/go/v1`.
- **Results:** `deepseek-v4-flash` (default) **13/14 (93 %), ~9.9 min** vs
  `kimi-k2.6` (fast-tier candidate) **12/14 (86 %), ~16.4 min**.
- Failures: `whattodo-1-restock-glucojoy` failed on **both** models
  (non-PENDING_APPROVAL status — shared spec-level behavior, not
  model-specific); `why-3-promo-delhi` timed out (180 s agent timeout) on
  kimi only.
- **Decision: keep deepseek-v4-flash**; refutes the original assumption in
  APPROACH.md #4 ("flash is overkill") for the current catalog.
- Reproduce commands; also documents the `AGENT_MODEL` vs `MODEL_NAME` env
  bug (`.env.example` documented a var that pydantic-settings never consumed
  — fixed in `306cba9`). **Great article anecdote: doc bug found while
  benchmarking.**

### 2.7 `docs/adr/` — six ADRs + index (16 + ~42–46 lines each)
| ADR | Title | Summary |
|---|---|---|
| 001 | Single-agent tool loop | One LangGraph agent + tool loop instead of multi-agent supervision (latency/tokens/state) |
| 002 | Star schema + null-with-flags | Sentinel/negative units nulled and flagged, not removed (auditable reconciliation) |
| 003 | QStash over RQ | Managed queue + signed webhook vs self-hosted worker; migration cost acknowledged (limitation #8) |
| 004 | Semantic caching | Cosine ≥ 0.97, TTL 600 s, hot-cache promotion, all-or-nothing invalidation |
| 005 | PII redaction pipeline | Deterministic redaction of phones/emails/names before LLM/vector store |
| 006 | Model choice | deepseek-v4-flash kept — benchmark beat kimi-k2.6 on accuracy and wall time |

Each ADR has Status / Context / Decision / Consequences / Alternatives
considered. → **The article can reference "the project records decisions as
ADRs" as a practice worth copying.**

### 2.8 `Data/DATA_DICTIONARY.md` (96 lines)
Field-level dictionary for all 8 tables (fact_primary_sales, fact_targets,
stockouts, promotions, dim_sku, dim_geo, dim_rep, dim_distributor).

### 2.9 `task_plan.md` (37 lines) — the superseded plan
Original RQ plan (Redis + RQ + Docker Compose, concurrency 5, TTL 10 min,
0.97, 10+ tests). Was gitignored mid-execution (`a44a670`). Article value:
the plan-vs-reality contrast (see LESSONS_LEARNED §1).

### 2.10 `working_prompts/` — the prompt trail
`agent.md` (64 lines, includes the Bugs list — retry history), `review.md`,
`structured.md`, `cache_queues.md` (the RQ→QStash swap instruction),
`embedding.md`, `eda/eda-prompt.md`, `eda/eda-findings.md` (389 lines),
`eda/2_data_cleaning.md`. → Raw evidence for the "AI-tooling constraints"
narrative; quote sparingly.

### 2.11 Source layout (for the "how it's built" section)
`src/api/main.py` (FastAPI: `/ask`, `/ask-direct`, `/webhook/process`,
`/cache/invalidate`, `require_api_key` dependency), `src/agent/`
(graph.py, config.py, tools, prompts/system.md, response models),
`src/cache/`, `src/internal/db/`, `scripts/` (clean_docs, preprocess,
generate_embeddings, eda_script, analyze_sales_value_patterns),
`tests/` (test_api, test_api_auth, test_cache, test_clean_docs),
`tests/evals/` (golden_questions.json + run_evals.py + policy checks),
`ui/index.html` (132-line minimal chat UI), `db.sql`, `Dockerfile`,
`embeddings.jsonl`.

---

## 3. Key facts & numbers (with sources)

| Number | Value | Source |
|---|---|---|
| Dataset | 8 CSV tables, 52 weeks, 5 categories, 12 territories | APPROACH.md |
| Unstructured docs | 30 text files (emails/notes/circulars) | APPROACH.md §3 |
| Cleaned rows | 61,932 (60,426 flagged `ok`; 1,506 sentinel/negative) | ARTEFACT.md |
| National 52-week primary sales | 38,630,596 units | ARTEFACT.md |
| Date formats found | 4 → normalized (10,972 rows) | APPROACH.md §0 |
| Non-numeric values | 9,416 rows (`"Rs 1,234"`) | APPROACH.md §0 |
| Sentinel 9999 / -9999 | 771 / 1 rows → NULL + flag | APPROACH.md §0 |
| Negative units | 734 rows → NULL + flag | APPROACH.md §0 |
| Duplicate fact rows | 23 pairs omitted to `omitted/` | ARTEFACT.md |
| PII redactions | 12 (4 names, 4 emails, 4 phones) | ARTEFACT.md |
| Synthetic-value finding | value ≈ 0.75×MRP×units in 54,853/59,348 rows | DATA_QUALITY.md §11 |
| Value/units inconsistency | 15–16 rows | DATA_QUALITY.md §10 |
| Evals golden set | 14 Q (WHAT×5, WHY×4, WHAT_TO_DO×3, OOD×2) | tests/evals/ |
| Benchmark | flash 13/14 93 % ~9.9 min vs kimi 12/14 86 % ~16.4 min | MODEL_BENCHMARK.md |
| Agent timeout | 180 s | APPROACH.md §5 |
| Cache | cosine ≥ 0.97, TTL 600 s | APPROACH.md §7 |
| Tests | 96 passing (baseline before showcase work: 70) | `unittest discover -s tests` |

---

## 4. The story arc (suggested narrative)

1. **Hook:** "I asked an AI to build a sales-intelligence agent over a messy
   FMCG dataset — then I benchmarked the AI's model choice with the agent it
   built." Or: the data-quality audit that proved ~92 % of the dataset was
   synthetic — a cautionary tale for anyone trusting sample data.
2. **What was built:** plain-English questions → SQL/vector-backed cited
   answers; WHAT / WHY / WHAT_TO_DO semantics; async queue; semantic cache.
3. **The data reality:** 4 date formats, `"Rs 1,234"` strings, 9999 sentinels,
   negatives-as-returns ambiguity, 23 duplicate rows, PII in business notes →
   null-with-flags + redaction + omitted-row audit trail.
4. **The process failure:** plan said RQ + Docker Compose; deploy target was
   Vercel serverless; mid-development pivot to QStash; AI-credit budget blown;
   review loops dropped. Lessons: lock infra before coding, budget review,
   prompt-retry discipline, 2–3× token provisioning.
5. **The measurement turn-around:** golden-set evals + policy checks +
   live benchmark; flash beat the "fast" candidate; env-var doc bug found;
   hypothesis in APPROACH.md refuted by data.
6. **The hardening pass:** anomalies catalogued, ADRs written, API secured
   (X-API-Key, constant-time compare, webhook exempt), tests consolidated,
   README rewritten. 70 → 96 tests.
7. **Practices a reader should copy:** ADRs for AI-made decisions, null-with-
   flags over deletion, eval golden sets with policy checks, micro-commits,
   reviewer passes per change, documentation-as-evidence (commit hashes in
   lessons learned).

---

## 5. Article target & format suggestions

- Suggested length: 1,500–3,000 words (or two parts). Include at least the
  architecture diagram (mermaid in APPROACH.md renders on GitHub; for
  external platforms, recreate as image), the QStash sequence diagram, and a
  data-quality table.
- Headline candidates: *"I Built a Sales-Intelligence Agent With an AI — Then
  Audited Its Data"*, *"What a Sample Dataset Taught Me About Data Quality"*,
  *"An AI Built This — Here's What Went Wrong (and What I Measured)"*.
- Honesty framing: the repo already contains the failures (APPROACH.md
  limitations, LESSONS_LEARNED.md). The article should not hide them; they
  are the most credible part.
- Attribution: one line that it originated as a university assignment over a
  sample dataset, reworked as a portfolio project (mirrors README footnote).
- Do NOT mention or include: `.env` contents, API keys, QStash/Gemini
  credentials, the live endpoint URL with a key, or any personal PII from
  `Data/docs/` (they contain real-looking names/phones/emails — the article
  must only describe the redaction, never reproduce the originals).

---

## 6. Issue-by-issue tracing (showcase work, with reviewers)

Every task followed: worker subagent (model `opencode-go/deepseek-v4-flash:max`)
→ 1 reviewer pass (max 2) → close with commit references. All on `develop`,
nothing pushed.

| Issue | Commits (worker) | Reviewer verdict + fixes |
|---|---|---|
| #2 DATA_QUALITY.md | `f841217` | FIXED `42e9538` (16 non-reproducible counts) |
| #3 evals | `0d7446d`, `440f8ba`, `2f44d42`, `fdcdfd6` | APPROVED (policy checks match AgentResponse contract) |
| #4 cache invalidation | `123c8df`, `c9db073`, `951e32f` | APPROVED |
| #6 model benchmark | `38cf9e1`, `306cba9` | APPROVED |
| #7 lessons learned | `9aed24d` | FIXED `4aff6e0` (RQ→QStash pivot narrative contradicted repo evidence) |
| #10 ADRs | `27bce24` | FIXED `16c152a` (ADR-003 narrative aligned) |
| #11 API auth | `5abc7b3`, `8765bed`, `2c5a6a1`, `200834b` | FIXED `1ce866c` (non-ASCII key crashed — bytes compare), `0ae5607`, `91d456e` |
| #8 test consolidation | `6e1fe43`, `bca454a` | APPROVED |
| #12 README rewrite | `85131ba` | APPROVED |

Also: `d30d5b0` (gitignore `.pi/` subagent artifacts). Reviewers caught real
defects in 4/9 tasks — a data point for the article's "review loops matter"
argument.

---

## 7. Human process facts (for the methodology section)

- **Orchestration:** one orchestrating agent (this project) dispatching
  worker subagents per GitHub issue; every issue = 1 worker + 1 reviewer;
  micro-commits with conventional messages; closing an issue requires the
  reviewer verdict and commit hashes in the comment.
- **Model discipline:** all subagents pinned to
  `opencode-go/deepseek-v4-flash:max` (the benchmarked winner) — a nice
  closing loop for the article: *the project applies its own benchmark
  result to its own development process*.
- **Tooling quirk (candid):** parallel worktree children silently dropped the
  model override (fell back to a provider with no API key) → sequential runs
  used instead. Evidence: first parallel dispatch failed with
  "No API key found for openai-codex"; workaround documented in this
  project's session memory.
- **No push policy:** all 26 commits remain local until the user approves.

---

## 8. Timeline (complete, for the article's chronology)

| Date | Event | Evidence |
|---|---|---|
| Jul 2 – Aug 3 | Repo scaffolded, Cadra/opencode configured, prompts added | LESSONS_LEARNED Phase 0 |
| Aug 5 02:00–04:00 | Core agent built (cleaning, vector store, tools, LangGraph loop, /ask) in ~15 small commits | `b2af573`→`1158f25` |
| Aug 5 16:07 | Queue+cache work starts per RQ plan | `task_plan.md`, `6e02ad7` |
| Aug 5 16:08 | RQ→QStash swap instruction lands (~2 min after deps) | `7aa1e22` |
| Aug 5 16:07–16:46 | QStash implementation + Vercel entrypoint + signing-key fix; unused deps dropped | `ed140a1`, `30cfd66`, `ff8ccf4`, `75ee659`, `df06007` |
| Aug 5 18:00–19:30 | Response-policy fixes; APPROACH/ARTEFACT docs; first AI-constraints doc | `4a759b5`, `6cdf834`→`b9eadce`, `1c3133b` |
| Aug 6–12 | README update; **showcase pass**: anomaly catalogue, evals, benchmark, cache invalidation, lessons, ADRs, API auth, test consolidation, README rewrite (26 commits) | `06b343b`, `f841217`→`85131ba` |
| Aug 12 | Benchmark executed: flash 13/14 93 % ~9.9 min vs kimi-k2.6 12/14 86 % ~16.4 min | MODEL_BENCHMARK.md |
| Future | UI design + implementation (issues #9, #13) in a separate session | open issues |

---

## 9. What exists vs what's missing (docs inventory)

**Exists (verified):** README.md, APPROACH.md, ARTEFACT.md,
Data/DATA_DICTIONARY.md, docs/DATA_QUALITY.md, docs/LESSONS_LEARNED.md,
docs/MODEL_BENCHMARK.md, docs/adr/ (README + 001–006), task_plan.md
(superseded), working_prompts/ (6 files + eda/), db.sql, Dockerfile,
ui/index.html, tests/evals/, this handoff.

**Missing (write these as part of or before the article):**

1. **`docs/ARTICLE.md` (or blog post)** — the main deliverable this handoff
   feeds. Does not exist yet.
2. **Architecture images** — APPROACH.md diagrams are mermaid (render on
   GitHub only). For external platforms, export the architecture diagram and
   QStash sequence diagram as PNG/SVG. Not committed anywhere yet.
3. **Screenshots** — no screenshots of the API docs (`/docs`), a sample
   agent response JSON, or `ui/index.html` exist. Take them for the article
   (local run: `uvicorn src.api.main:app --reload`).
4. **Deployment/run guide** — README covers local quickstart; there is no
   Vercel deployment walkthrough doc (relevant once #9/#13 land). Optional
   for the article; can be a follow-up section.
5. **`LICENSE`** — no license file in the repo. Decide (MIT suggested for
   portfolio) before making the article public; note it in the article.
6. **`CHANGELOG.md`** — doesn't exist; the commit chain + issue history is
   the de-facto changelog. Optional to add for the public repo.
7. **Issue #9/#13 (UI)** — the showcase UI is not built; the article should
   either describe the current `ui/index.html` (132-line minimal chat page)
   or defer UI screenshots until the UI session completes.

---

## 10. Writing instructions for the article agent

1. Read §2 files in the repo before drafting. Prefer direct quotes from
   APPROACH.md/LESSONS_LEARNED.md for the failure narrative; they are
   already public-ready and honest.
2. Structure suggestion (adapt freely):
   - TL;DR / what is SSI
   - The data (and why it was hard)
   - The architecture (agent loop, queue, cache — with diagrams)
   - What went wrong (pivot, AI-tooling constraints, budget)
   - What we measured (evals, benchmark — tables)
   - What we changed (hardening pass, ADRs, auth, 70→96 tests)
   - Lessons + practices worth copying
   - Appendix: doc map + commit chain
3. Tone: first-person engineering narrative, concrete numbers, no hype.
4. Length: 1,500–3,000 words or a two-part series; keep code blocks minimal
   (the API curl example and one response JSON).
5. Deliverable: `docs/ARTICLE.md` (or `docs/ARTICLE_PART1.md` + `_PART2.md`)
   committed with a conventional message (`docs: draft public process article`).
   Do not push.

---

## 11. Fact-check checklist (verify before declaring done)

- [ ] Every number in the article matches its source file (§3 table).
- [ ] "~92 % synthetic" claim: recompute from DATA_QUALITY.md §11
  (54,853/59,348) — phrase it as "the audit found…", not as an accusation.
- [ ] Benchmark numbers (13/14 vs 12/14; 9.9 vs 16.4 min) match
  MODEL_BENCHMARK.md.
- [ ] No API keys, tokens, `.env` values, or live-endpoint credentials appear.
- [ ] No PII from Data/docs/ is reproduced (only the redaction mechanism).
- [ ] Commit hashes cited in the article exist: `git cat-file -t <hash>`.
- [ ] Issue numbers/statuses match `gh issue list --state all`.
- [ ] Test count claim (96) verified by running the suite once.
- [ ] ADR titles/statuses match docs/adr/README.md index.
- [ ] README provenance footnote wording respected (assignment origin, one
  line, honest).
