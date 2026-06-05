# Notes — Chapter 20

## Connections

`redis.asyncio.from_url` returns a *client* backed by a connection pool.
Reuse one client per process. Closing/recreating it per request kills
performance.

## Memory model

Redis is in-memory; keys evicted when `maxmemory` is hit. Choose a
sensible eviction policy:
- `allkeys-lru` for caches
- `noeviction` for queues / persistent data
- `volatile-ttl` if you set TTLs on the right keys

## Persistence

- RDB: periodic snapshots. Fast restart, possible data loss.
- AOF: append-only log. Slower writes, less loss.
- Use **Redis Cluster** or **managed Redis** in production.

## Pitfalls

- Big keys (1 MB+) — slow to fetch, block other clients. Split.
- `KEYS *` scans EVERY key. Use `SCAN` in production.
- `MULTI/EXEC` is atomic per connection — pool reuse can cross transactions.

## Vector search?

We do `26_vector_search` with NumPy. Redis Stack also offers HNSW
vector indices via `FT.CREATE`/`FT.SEARCH` — great when you already
have Redis and want a single dependency.
