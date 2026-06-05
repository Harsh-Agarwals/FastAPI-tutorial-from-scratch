"""
Chapter 21 — Task Queues (the durable kind).

We build a *minimal* Redis-backed queue end-to-end so you understand
how Celery / RQ / Dramatiq work under the hood:

  producer (FastAPI) ──▶  Redis list (queue)  ──▶  worker process(es)
                              │
                              ▼
                       Redis hash (job state)

Patterns shown:
- enqueue + job id returned (202)
- worker process polls with BLPOP (blocking pop)
- retry with backoff on failure
- dead-letter queue (DLQ)
- separate worker entrypoint

Run:
    docker run -d --name redis -p 6379:6379 redis:7
    uvicorn 21_task_queues.app:app --reload --port 8000
    python -m 21_task_queues.worker     # in another terminal
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = "queue:summarize"
DLQ = "queue:summarize:dlq"
STATE_PREFIX = "job:"

# How many times before we shovel into the DLQ.
MAX_RETRIES = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    try:
        yield
    finally:
        await app.state.redis.close()


app = FastAPI(title="Chapter 21 — Task Queues", lifespan=lifespan)


class EnqueueIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


@app.post("/jobs", status_code=202)
async def enqueue(payload: EnqueueIn) -> dict:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "text": payload.text,
        "status": "queued",
        "attempts": 0,
        "submitted_at": time.time(),
    }
    pipe = app.state.redis.pipeline()
    pipe.hset(STATE_PREFIX + job_id, mapping={k: json.dumps(v) for k, v in job.items()})
    pipe.rpush(QUEUE, json.dumps({"id": job_id}))
    await pipe.execute()
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
async def status(job_id: str) -> dict:
    data = await app.state.redis.hgetall(STATE_PREFIX + job_id)
    if not data:
        raise HTTPException(404, "unknown job")
    return {k: json.loads(v) for k, v in data.items()}


@app.get("/queue/depth")
async def depth() -> dict:
    main = await app.state.redis.llen(QUEUE)
    dlq = await app.state.redis.llen(DLQ)
    return {"queue": main, "dlq": dlq}


@app.post("/queue/replay-dlq")
async def replay_dlq() -> dict:
    """Move every job out of the DLQ back into the main queue."""
    moved = 0
    while await app.state.redis.lmove(DLQ, QUEUE, "LEFT", "RIGHT"):
        moved += 1
    return {"moved": moved}
