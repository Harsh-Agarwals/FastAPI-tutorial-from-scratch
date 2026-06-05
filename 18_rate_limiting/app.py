"""
Chapter 18 — Rate limiting.

Why: prevent abuse, protect upstreams, control cost. Especially
critical for AI endpoints that map directly to dollars per call.

We implement three approaches side by side:

1. **In-memory token bucket** (good for one process, learning).
2. **Redis-based sliding window** (multi-process safe).
3. **slowapi** (battle-tested library) for production-shaped use.

Run:
    redis-server &           # or via docker (see README)
    uvicorn 18_rate_limiting.app:app --reload --port 8000
"""
from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Request, status
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# (1) In-memory token bucket. One bucket per identity (IP here).
# Not safe across processes. Demonstrative only.
# ---------------------------------------------------------------------------
class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = capacity
        self.last = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


_buckets: dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(capacity=5, refill_per_sec=1))


async def in_memory_limit(request: Request) -> None:
    ident = request.client.host if request.client else "anon"
    if not _buckets[ident].allow():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded (in-memory)")


# ---------------------------------------------------------------------------
# (2) Redis sliding-window limiter. Safe across many workers / machines.
# Algorithm: store request timestamps in a sorted set; trim old ones; count.
# ---------------------------------------------------------------------------
LUA_SLIDING_WINDOW = """
local key   = KEYS[1]
local now   = tonumber(ARGV[1])
local win   = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- drop entries older than `now - win`
redis.call('ZREMRANGEBYSCORE', key, 0, now - win)
local count = tonumber(redis.call('ZCARD', key))
if count >= limit then
  return 0
end
redis.call('ZADD', key, now, now .. ':' .. math.random())
redis.call('PEXPIRE', key, win)
return 1
"""

# ---------------------------------------------------------------------------
# (3) slowapi — production-friendly. Plays well with FastAPI.
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Chapter 18 — Rate Limiting")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _slowapi_handler(request, exc):
    raise HTTPException(429, f"slowapi: too many requests ({exc.detail})")


redis: aioredis.Redis | None = None


@app.on_event("startup")
async def _startup() -> None:
    global redis
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    # Ping so we fail fast if Redis is down.
    try:
        await redis.ping()
    except Exception as e:
        print(f"Redis unavailable: {e}. The /redis-* routes will 500.")


async def redis_sliding_window(
    request: Request, limit_per_min: int = 10
) -> None:
    if redis is None:
        raise HTTPException(503, "Redis not initialised")
    ident = request.client.host if request.client else "anon"
    key = f"rl:{request.url.path}:{ident}"
    now_ms = int(time.time() * 1000)
    window_ms = 60_000
    ok = await redis.eval(LUA_SLIDING_WINDOW, 1, key, now_ms, window_ms, limit_per_min)
    if ok == 0:
        raise HTTPException(429, "Rate limit exceeded (Redis sliding window)")


@app.get("/in-memory", dependencies=[Depends(in_memory_limit)])
def in_memory():
    return {"ok": True, "limiter": "in-memory token bucket"}


@app.get("/redis-limited", dependencies=[Depends(redis_sliding_window)])
async def redis_limited():
    return {"ok": True, "limiter": "redis sliding window"}


@app.get("/slowapi-limited")
@limiter.limit("5/minute")
def slowapi_limited(request: Request):
    return {"ok": True, "limiter": "slowapi (5/min per IP)"}
