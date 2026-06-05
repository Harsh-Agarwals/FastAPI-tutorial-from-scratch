"""
Chapter 20 — Redis from a FastAPI perspective.

A focused tour of the Redis primitives we use elsewhere:
- strings (cache, counters)
- hashes  (small structured records)
- lists   (queues — chapter 21)
- sets    (uniqueness)
- sorted sets (rate limiting, leaderboards)
- pub/sub (cross-instance broadcast)
- TTL + EXPIRE

We use `redis.asyncio` so handlers stay non-blocking.

Run:
    docker run -d --name redis -p 6379:6379 redis:7
    uvicorn 20_redis_intro.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        await app.state.redis.ping()
    except Exception as e:
        # Fail loudly at startup if Redis is unreachable.
        raise RuntimeError(f"Redis not reachable at {REDIS_URL}: {e}")
    try:
        yield
    finally:
        await app.state.redis.close()


app = FastAPI(title="Chapter 20 — Redis Intro", lifespan=lifespan)


# --- Strings + counters -----------------------------------------------------
@app.post("/string/{key}")
async def set_string(key: str, value: str, ttl: int | None = None) -> dict:
    if ttl is not None:
        await app.state.redis.set(key, value, ex=ttl)
    else:
        await app.state.redis.set(key, value)
    return {"key": key, "value": value, "ttl": ttl}


@app.get("/string/{key}")
async def get_string(key: str) -> dict:
    v = await app.state.redis.get(key)
    if v is None:
        raise HTTPException(404, "key not found")
    return {"key": key, "value": v}


@app.post("/counter/{name}")
async def incr_counter(name: str) -> dict:
    n = await app.state.redis.incr(f"counter:{name}")
    return {"counter": name, "value": n}


# --- Hashes ------------------------------------------------------------------
@app.post("/hash/{key}")
async def set_hash(key: str, payload: dict[str, str]) -> dict:
    await app.state.redis.hset(key, mapping=payload)
    return {"key": key, "fields": list(payload.keys())}


@app.get("/hash/{key}")
async def get_hash(key: str) -> dict:
    data = await app.state.redis.hgetall(key)
    if not data:
        raise HTTPException(404, "key not found")
    return {"key": key, "data": data}


# --- Sorted sets (great for leaderboards / rate limits) ---------------------
@app.post("/zadd/{key}")
async def zadd(key: str, member: str, score: float) -> dict:
    await app.state.redis.zadd(key, {member: score})
    return {"ok": True}


@app.get("/ztop/{key}")
async def ztop(key: str, n: int = 5) -> dict:
    return {"top": await app.state.redis.zrevrange(key, 0, n - 1, withscores=True)}


# --- Pub/Sub (cross-instance broadcast) -------------------------------------
@app.post("/publish/{channel}")
async def publish(channel: str, message: str) -> dict:
    subs = await app.state.redis.publish(channel, message)
    return {"subscribers": subs}


@app.get("/subscribe-once/{channel}")
async def subscribe_once(channel: str, timeout_s: float = 5.0) -> dict:
    """Wait for ONE message on `channel` then return."""
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                return {"channel": channel, "data": msg["data"]}
            await asyncio.sleep(0)
        raise HTTPException(504, "no message in time")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
