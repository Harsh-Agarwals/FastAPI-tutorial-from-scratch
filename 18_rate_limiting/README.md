# 18 — Rate Limiting

Three patterns, ranked by realism.

| Limiter                   | Across processes? | Across machines? | Algorithm           |
|---------------------------|:----------------:|:----------------:|---------------------|
| In-memory token bucket    | ✗                | ✗                | token bucket        |
| Redis sliding window      | ✓                | ✓                | sliding window (Lua)|
| slowapi (Redis backed)    | ✓                | ✓                | wraps Redis/Memcache|

## Why care?

- **Abuse / DoS** — one client should not melt your fleet.
- **Upstream protection** — OpenAI has its own quota; respect it.
- **Cost control** — AI calls cost money per token.
- **Fair use** — protect normal users from a noisy neighbour.

## Run

```bash
docker run -d --name redis -p 6379:6379 redis:7
uvicorn 18_rate_limiting.app:app --reload --port 8000

# Hit each one 10 times in a loop and watch some return 429.
for i in {1..10}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/slowapi-limited; done
```

## Algorithms in one sentence each

- **Fixed window** — count per minute window. Simple; suffers from
  bursts at boundary.
- **Sliding window** — count over the last N seconds at any instant.
  Smoother, slightly more state.
- **Token bucket** — refills tokens at a steady rate; allows bursts up
  to capacity. Great UX.
- **Leaky bucket** — like token bucket but enforces a constant outflow.

## Identity matters

Per-IP is the easy default but trivially bypassed. Real systems
combine layers:

- per-IP at the edge (Cloudflare / WAF)
- per-API-key in the app
- per-user-id once authenticated
- per-tenant for multi-tenant SaaS

## Why a Lua script in Redis?

Atomicity. We trim old entries, count, and (maybe) add a new entry in
**one** round trip. Two separate Redis calls would race.

## Headers to set on 429

The polite response includes:

- `Retry-After: <seconds>` — when the client should try again.
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` —
  let well-behaved clients self-throttle.

## Exercises

1. Add `Retry-After` to your 429 responses.
2. Move the limit key from IP to a header `X-Tenant-Id`.
3. Implement a hybrid: 100/min per IP **and** 10/min per tenant, both
   must allow the request.
