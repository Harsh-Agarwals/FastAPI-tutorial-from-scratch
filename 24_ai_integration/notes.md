# Notes — Chapter 24

## Failure modes you will see

- 429 rate limit (provider) — back off, jitter.
- 500 / 503 upstream — retry a couple of times.
- Streaming connection drop — resume or restart.
- Slow tokens (>10s for a sentence) — timeout + show "still thinking".
- Content policy refusal — handle as a normal alternative answer.

## Cost budgeting

Track tokens, not requests. The same endpoint can cost 100x more
depending on input. Expose a `daily_tokens` quota per tenant.

## Prompt injection

If a user-provided string is concatenated into a system prompt,
treat it as adversarial. Sanitise, or use the API's separate
`messages` shape with `role=user`.

## Determinism

`temperature=0` is *less* random, not deterministic. For repeatable
tests, mock the LLM.

## Observability

Log per request: model, prompt hash, latency, tokens in/out. Avoid
logging the prompt itself unless you have user consent.
