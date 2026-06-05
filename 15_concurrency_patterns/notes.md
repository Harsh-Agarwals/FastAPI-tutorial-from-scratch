# Notes — Chapter 15

## How to pick a pattern

- "Run N things, all are independent." → fan-out + gather
- "Many items, each can be processed by any of K workers." → worker pool
- "Multi-step transformation with rate mismatches." → pipeline
- "Multiple upstreams, must not interfere." → bulkhead
- "Calls are expensive per-call, items are cheap." → batching

## Backpressure beats retries

If your queue is full, slow down upstream. Don't accept more work and
retry: you'll just amplify the failure (the "thundering herd" problem).

## Idempotency

Whenever you retry, design for idempotency: same key → same effect.
This is gold for AI workflows where partial output is common.
