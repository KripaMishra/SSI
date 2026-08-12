# ADR-004: Semantic caching with TTL and similarity threshold

## Status

Accepted (implemented; see APPROACH.md §7).

## Context

Per-question agent latency is ~36–46s (see ADR-006), and users re-ask near-identical
questions (paraphrases, follow-ups on the same topic) over a static dataset. Exact
string caching cannot help because natural-language questions rarely match
byte-for-byte. Limitation #3 in APPROACH.md documents the cache's invalidation
design.

## Decision

Cache agent responses semantically in Redis:

1. Embed the question with `gemini-embedding-2` (1536d).
2. On lookup, return the cached response if the highest cosine similarity to a
   stored question is **≥ 0.97**.
3. Store responses in Redis hashes with a **600s default TTL**; a cache hit
   refreshes the TTL (hot-cache promotion).
4. Invalidate explicitly via `POST /cache/invalidate` on data-update events; TTL
   remains as a backstop.

## Consequences

- **Positive**: paraphrased repeats are served in one round-trip instead of a
  ~40s agent run; hot topics stay hot; invalidation is available for data updates.
- **Negative**: invalidation is all-or-nothing — no selective key invalidation;
  the endpoint is unauthenticated (API auth tracked as issue #11); a false hit
  above the 0.97 threshold would silently serve stale/incorrect answers;
  pre-synthesizing responses for frequent topics is deferred future work.

## Alternatives considered

- **Exact-match cache**: rejected — useless for paraphrases and follow-ups.
- **No cache**: rejected — every repeat question pays full agent latency and
  tokens.
- **LLM-judged similarity at lookup time**: rejected — adds a model call per
  request, defeating the purpose.
- **Standalone vector DB for the cache**: rejected — ChromaDB is already used for
  document retrieval, but the cache needs fast KV semantics with TTL, which Redis
  provides.
