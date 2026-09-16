# ADR-008: Command Code Provider API for agent inference

## Status

Accepted.

## Context

The agent's LLM calls went through an opencode-go (Zen) endpoint configured with
`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `MODEL_NAME`. That backend is a separate
subscription from the Command Code CLI used to build the project, its model ids
(`deepseek-v4-flash`) are not portable, and the account ran out of credit mid-development,
which surfaced as `AuthenticationError: CreditsError` in the live agent path.

Command Code exposes a Provider API — an OpenAI- and Anthropic-compatible endpoint over the
same model catalog the CLI serves — and every plan except **Go** has API access, metered
against that plan's credits (see [provider docs](https://commandcode.ai/docs/provider)).

## Decision

Point agent inference at the Command Code Provider API:

1. `OPENAI_BASE_URL=https://api.commandcode.ai/provider/v1` (OpenAI Chat Completions wire,
   so `ChatOpenAI` is unchanged) with `OPENAI_API_KEY` set to a Command Code API key created
   in Studio → API keys — one credential for the CLI and the API.
2. `MODEL_NAME=deepseek/deepseek-v4-flash` — the benchmarked default (ADR-006), using the
   provider's exact, namespaced id.
3. `AGENT_REASONING_EFFORT` is now consumed (`AgentConfig.reasoning_effort`, default `high`),
   because the catalog pins a valid effort set per model and `deepseek-v4-flash` advertises
   only `high | max` — the previously hardcoded `"low"` is not in that set.

## Consequences

- **Positive**: one key and one bill for CLI and service; the whole top-model catalog behind a
  single OpenAI-compatible endpoint; API usage meters against existing plan credits rather
  than a second subscription; per-request usage and cost are visible in Studio.
- **Negative**: model ids must be the namespaced ones, and they are plan-scoped — a model the
  plan lacks returns `403 upgrade_required`; the wire is model-bound (Anthropic ids need
  `/v1/messages`, so a Claude move would also need a different client); reasoning effort must
  match the model's advertised set or the request can 400; eval runs and worker retries now
  spend real plan credits.

## Alternatives considered

- **Stay on opencode-go**: rejected — a second subscription, non-portable ids, and its
  exhausted credits already broke the live agent path.
- **Keep both backends behind a flag**: rejected — the harness talks plain OpenAI-compatible
  HTTP either way, so a flag would only encode which vendored key filled the same two vars.
- **A different aggregator (OpenRouter, Vercel AI Gateway)**: viable but rejected — the CLI
  and the service would still be billed twice, and this keeps one credential for both.
