"""
Chapter 19 — Caching.

For an AI backend, caching is *the* lever for cost and latency. The
same prompt asked twice should not cost money twice.

We implement three layers:
1. `functools.lru_cache` — process-local, simplest.
2. In-memory dict with TTL — process-local, evictions explicit.
3. Redis cache — shared across workers / machines.

Plus the *cache-aside* pattern: the canonical "check cache, miss → fetch,
store, return".

Run:
    uvicorn 19_caching.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from functools import lru_cache
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(title="Chapter 19 — Caching")
redis: aioredis.Redis | None = None


@app.on_event("startup")
async def _startup() -> None:
    global redis
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)


# ---------------------------------------------------------------------------
# (1) lru_cache — small, hot, deterministic functions
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1024)
def _slow_pure(n: int) -> int:
    """Imagine a deterministic heavy computation."""
    time.sleep(0.2)  # we deliberately block so the win is obvious
    return n * n


@app.get("/lru/{n}")
async def lru(n: int) -> dict:
    t = time.perf_counter()
    # `_slow_pure` is synchronous; for demonstration we just call it.
    val = _slow_pure(n)
    return {"value": val, "ms": int((time.perf_counter() - t) * 1000), "cache": "lru_cache"}


# ---------------------------------------------------------------------------
# (2) In-memory cache with TTL
# ---------------------------------------------------------------------------
class TTLCache:
    def __init__(self, default_ttl_s: float = 30):
        self._d: dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_s

    def get(self, key: str) -> Any:
        if (entry := self._d.get(key)) is None:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            self._d.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl_s: float | None = None) -> None:
        self._d[key] = (time.time() + (ttl_s or self.default_ttl), value)


memcache = TTLCache(default_ttl_s=10)


# Pretend external call (LLM, DB, etc).
async def expensive_call(query: str) -> dict:
    await asyncio.sleep(0.5)
    return {"echo": query.upper(), "tokens": len(query.split())}


def _key(prefix: str, query: str) -> str:
    h = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"{prefix}:{h}"


@app.get("/memcache")
async def memcache_route(q: str) -> dict:
    key = _key("ai", q)
    if hit := memcache.get(key):
        return {"hit": True, **hit}
    miss = await expensive_call(q)
    memcache.set(key, miss, ttl_s=10)
    return {"hit": False, **miss}


# ---------------------------------------------------------------------------
# (3) Redis cache — shared across workers
# ---------------------------------------------------------------------------
@app.get("/redis-cache")
async def redis_cache_route(q: str) -> dict:
    assert redis is not None
    key = _key("ai", q)
    raw = await redis.get(key)
    if raw:
        return {"hit": True, **json.loads(raw)}
    miss = await expensive_call(q)
    await redis.set(key, json.dumps(miss), ex=60)
    return {"hit": False, **miss}


# ---------------------------------------------------------------------------
# Bonus: "single-flight" — coalesce concurrent identical requests
# so they only hit the upstream once.
# ---------------------------------------------------------------------------
_inflight: dict[str, asyncio.Future] = {}
_inflight_lock = asyncio.Lock()


async def single_flight(key: str, factory):
    async with _inflight_lock:
        fut = _inflight.get(key)
        if fut is None:
            fut = asyncio.create_task(factory())
            _inflight[key] = fut

    try:
        return await fut
    finally:
        async with _inflight_lock:
            _inflight.pop(key, None)


@app.get("/single-flight")
async def single_flight_route(q: str) -> dict:
    key = _key("sf", q)
    result = await single_flight(key, lambda: expensive_call(q))
    return result
