# Lessons Learned — SSI Development Process

What went sideways during development, why, what it cost, and what to do
differently next time. Source material: git history (branch `develop`),
`task_plan.md` (the superseded RQ plan), `APPROACH.md` §6 and limitations
#8/#9, and `working_prompts/cache_queues.md` (the swap instruction).

---

## 1. Timeline: what changed mid-project and why

All work below happened in one marathon session on **2026-08-05** unless
noted. Commit hashes are the evidence trail.

### Phase 0 — Bootstrap (Jul 2 – Aug 3)
Repo scaffolded, Cadra/opencode configured with a proxy backend, prompt
files added. No application code.

### Phase 1 — Core agent (Aug 5, 02:00–04:00)
Data cleaning + ingestion → vector store → retrieval tools →
LangGraph single-agent loop → `/ask` endpoint. Committed as ~15 small
conventional commits (`b2af573` → `1158f25`). This phase went well: small
steps, one concern per commit.

### Phase 2 — Queue + cache per plan (Aug 5, 16:07)
`task_plan.md` was the plan: **Redis semantic cache + python-rq queue +
Docker Compose** (`ssi-api`, `ssi-worker`, `redis` services, concurrency 5,
TTL 10 min, 0.97 cosine threshold, 10+ tests). Commits:
- `6e02ad7` build: add cache queue dependencies (`rq`, `redis`, `numpy`)
- `ed140a1` feat(cache): semantic response cache
- `30cfd66` feat(api): queue cached ask requests
- `f912837` build: add API container (docker-compose)
- `7aa1e22` chore(prompt): add cache queue prompt
- `a44a670` chore: ignore task plan (the RQ plan was **gitignored**)
- `107634f` / `e44d8bf` tests for queue flow and cache matching

### Phase 3 — Mid-development pivot: RQ → QStash (Aug 5, 16:07–16:46)
~40 minutes after the queue work started, the stack was swapped:
- `working_prompts/cache_queues.md` instructs: *"Swap the redis with
  upstash instance of redis; swap the rq with QStash"* — Upstash Redis +
  QStash with a webhook receiver
- `ff8ccf4` chore(api): add default entrypoint for vercel deployment —
  the deployment target is **Vercel serverless**, where a long-running RQ
  worker and docker-compose cannot run
- `75ee659` chore: remove unused packages — RQ-era data-science deps
  (`numpy`, `pandas`, `scikit-learn`, `scipy`, `matplotlib`, `joblib`)
  dropped from `requirements.txt`
- `df06007` fix: fetch qstash signing key — webhook signature verification

**Why it changed:** the deployment constraint (Vercel serverless) makes a
self-hosted worker impossible. QStash is a managed queue that delivers to a
serverless webhook endpoint; Upstash Redis replaces self-hosted Redis for
the same reason. The plan in `task_plan.md` never considered the deploy
target — the constraint surfaced only when the docker-compose worker
couldn't ship.

**What it cost:** the RQ path was fully implemented, tested, and
docker-composed before being discarded. That design + implementation + test
effort was duplicated, not reused. APPROACH.md limitation #8 states it
directly: the migration *"burned AI credits and prevented dedicated review
loops"* — the session's remaining budget went to rework instead of review.

### Phase 4 — Fixes and documentation (Aug 5, 18:00–19:30)
Agent response-policy fixes (`4a759b5`), approach/artefact docs
(`6cdf834` → `b9eadce`), and `1c3133b` "doc: AI tooling constraints
experienced during development" — the first written acknowledgment of the
constraint problem, committed at the *end* of the session.

### Phase 5 — Follow-up (Aug 6–12)
README update (`06b343b`), eval runner + golden set (`0d7446d`,
`440f8ba`, `2f44d42`), model benchmark (`38cf9e1`, deepseek-v4-flash vs
kimi-k2.6), cache invalidation endpoint (`123c8df`). Done after the fact —
these were the review-loop activities the queue rework displaced.

---

## 2. AI-tooling constraints and their cost impact

From APPROACH.md #9 and `working_prompts/`:

| Constraint | Observed effect | Cost impact |
|---|---|---|
| **Retry prompts** — the model is capable on long tasks but repeatedly fails at reasoning, standard practices, and following explicit instructions | Multiple retry prompts per task; e.g. agent.md's Bugs list shows 6+ defects (citations in wrong field, hardcoded confidence, raw SQL instead of ORM, non-JSON responses) found one at a time | Each retry is a full task re-run; tokens consumed multiply (retry factor ~2–3× ideal) |
| **Text-only model** — no image input while debugging HTML | `approach.html`/`artefact.html` rendering issues could not be diagnosed by looking at the page; diagnosis was guess-and-retry | Extra retry cycles on UI work; the doc work at 19:02–19:18 (`2bd9db6`–`b9eadce`) shows the churn |
| **Token/request policy** — constrained AI budget, unplanned expenditure | The queue rework + retries blew through the allocation; APPROACH.md #9: the policy *"contributed significantly to unplanned token expenditure"* | Dedicated review loops were cut (limitation #8); constraints were documented only post-hoc at session end |
| **Missing resource availability** | #9: *"a better resource availability would have yielded better response"* | Quality ceiling on the final output — limitations and trade-offs were discovered late, not designed out |

Net effect: the session finished with the feature working but with the
cheapest-to-fix findings (deployment constraint, review gap, model
limitations) landing as documentation debt in APPROACH.md instead of being
prevented.

---

## 3. Process recommendations for future projects

1. **Lock queue/async infrastructure before writing code — and before
   choosing the deploy target.** Decide self-hosted worker vs. managed
   queue in the plan, not 40 minutes into implementation. Check the
   deployment platform's constraints first (Vercel serverless ⇒ no
   long-running workers ⇒ QStash/Upstash from day one). A `task_plan.md`
   should state the deploy target and the infra decision; a plan that is
   gitignored mid-execution is a warning sign the plan is already stale.
2. **Budget a dedicated review loop.** Reserve a fixed review pass
   (evals, benchmark, docs) separate from implementation, and don't let
   rework consume it. The eval runner + golden set + benchmark ended up as
   post-hoc work on Aug 6–12 because Aug 5's budget went to the queue
   pivot. Review-first would have caught the deploy constraint earlier.
3. **Use an image-capable model for UI debugging.** Screenshots beat
   guess-and-retry for HTML/CSS/render issues. If the model is text-only,
   scope UI work explicitly as "render + report the diff", not "debug the
   page".
4. **Prompt-retry discipline.** Before re-prompting, (a) state what
   changed, (b) require the model to state the assumption that failed, (c)
   cap retries per task (e.g., 2), then change strategy — smaller task,
   more context, or different model. Log retry prompts to
   `working_prompts/` as done here, so token waste is visible and auditable
   per milestone.
5. **Cost the swap before swapping.** The `cache_queues.md` style
   migration instruction was effective as an explicit directive, but
   mid-development stack swaps should estimate the duplicate work (design +
   implementation + tests) before committing to them. If the old path can
   be reused (e.g., Redis stays, only the worker changes), say so in the
   swap prompt.
6. **Pre-flight constraints into the repo, not the prompt.** The model was
   told it was *"strictly prohibited to read from the .env"* and had to
   probe keys via bash. Encode such constraints once in the README /
   `.env.example` (as `306cba9` later did for `MODEL_NAME`) instead of
   repeating them in every task prompt — that repetition is itself token
   cost and a failure point.
7. **Provision the token budget for retries.** Assume 2–3× the
   ideal-session tokens when estimating an AI-driven milestone; the ideal
   path (no retries, no rework) is not the realistic one. Under-provisioning
   is what turned the queue pivot into a dropped review loop.

---

## Reference points

- `task_plan.md` — original RQ plan (Redis + RQ + Docker Compose); gitignored at `a44a670`, superseded by the QStash design
- `APPROACH.md` §6 — final QStash architecture (sequence diagram)
- `APPROACH.md` limitations #8 (migration cost) and #9 (AI-tooling constraints)
- `working_prompts/cache_queues.md` — the RQ→QStash swap instruction
- `working_prompts/agent.md` — retry history (Bugs list) showing repeated-failure pattern
- Commit `1c3133b` — first documentation of AI-tooling constraints
