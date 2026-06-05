# 19 — Caching

If your AI service has *any* repeat prompts, a cache pays for itself
in minutes. We layer four techniques.

## 1. `lru_cache` (process-local, decorator)

```python
@lru_cache(maxsize=1024)
def expensive(args): ...
```

Best for **pure, deterministic** Python functions. No TTL, no
invalidation, no cross-process sharing.

## 2. In-memory TTL cache

A `dict[str, (expires_at, value)]`. Trivial, fast, single-process.

```python
if hit := cache.get(key):
    return hit
miss = await fetch()
cache.set(key, miss, ttl_s=60)
return miss
```

## 3. Redis cache (the real one)

Shared across uvicorn workers and replicas. Use `SET key value EX ttl`.
Two-step retrieval is OK in async; Redis is fast (~1 ms LAN).

## 4. Single-flight (a.k.a. request coalescing)

If 50 clients ask for the same uncached key at once, you want **one**
upstream call, not 50. We keep a `Future` keyed by request and await
the same one from every concurrent caller.

## Run

```bash
docker run -d --name redis -p 6379:6379 redis:7
uvicorn 19_caching.app:app --reload --port 8000

# First call slow, repeats fast
time curl 'http://localhost:8000/memcache?q=hello'
time curl 'http://localhost:8000/memcache?q=hello'

# Shared across workers via Redis
time curl 'http://localhost:8000/redis-cache?q=hello'
time curl 'http://localhost:8000/redis-cache?q=hello'

# Single-flight: hammer 50 concurrent requests — see backend logs
seq 50 | xargs -n1 -P50 -I{} curl -s 'http://localhost:8000/single-flight?q=same' > /dev/null
```

## Choosing a key

Hash a normalised representation of the input:

```python
key = "ai:" + sha256(prompt.strip().lower().encode()).hexdigest()[:16]
```

Normalise! `"Hello"` and `"hello "` should hit the same entry.

## Invalidation

The hard part. Options:

- **TTL** — easiest; accept some staleness.
- **Write-through** — every write to the source updates the cache.
- **Write-behind** — writes queue an async cache update (risky).
- **Versioned keys** — bump a version prefix when data shape changes.

Always include a way to bypass the cache for debugging
(e.g. `?no_cache=1` in dev).

## What to cache in AI services

- Final answers keyed on the normalised prompt + model + temperature.
- Embeddings (the vectors themselves rarely change).
- Tool call results (web fetches, RAG retrievals).
- **Don't cache** anything depending on per-user secret context unless
  you scope the key by user id.

## Exercises

1. Add a `?no_cache=1` query param to bypass on demand.
2. Add cache *stampede* protection: when an entry is about to expire,
   refresh it in the background while serving the stale value.
3. Track hit ratio and expose it on `/cache/stats`.
