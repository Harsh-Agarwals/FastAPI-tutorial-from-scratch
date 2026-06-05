"""
Chapter 30 — Scalability demo: a stateless FastAPI service designed
to scale horizontally.

There is intentionally no in-memory state. Every operation reads /
writes Redis. This is the "12-factor" shape.

Run with multiple workers:
    uvicorn 30_scalability_concepts.app:app --port 8000 --workers 4
"""
from __future__ import annotations

import os
import socket
import time

import redis.asyncio as aioredis
from fastapi import FastAPI
from contextlib import asynccontextmanager

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    yield
    await app.state.redis.close()


app = FastAPI(title="Chapter 30 — Stateless service", lifespan=lifespan)


@app.get("/who")
def who() -> dict:
    """Reports the worker that handled this request. Useful to verify load balancing."""
    return {
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "uptime_s": round(time.time() - app.extra.get("started", time.time()), 2),
    }


@app.post("/count")
async def count() -> dict:
    """A counter that is correct across many workers because state lives in Redis."""
    n = await app.state.redis.incr("global:count")
    return {"count": n}


app.extra = {"started": time.time()}
