# Notes — Chapter 18

## Where to enforce

- **Edge** (Cloudflare, ALB, nginx) — cheapest, hardest to bypass.
- **Gateway** — per-tenant, per-API-key.
- **App** — fine-grained, expensive endpoints (LLM calls).

Use all three layers in production.

## Latency cost

Each Redis call costs ~1 ms locally, ~5-20 ms in the cloud. For
extreme RPS, prefer:
- a local token bucket per worker that periodically syncs to Redis
- approximate counters (HyperLogLog) when exact counts aren't needed

## Bucket eviction

Don't let `_buckets` (in-memory) grow without bound. Use an LRU or a
TTL sweep. The in-memory example here intentionally skips that to
keep code short.

## Tests

A handy way to test: replace `time.monotonic` with a fake clock so
you can fast-forward without actually waiting.
