"""
Chapter 15 — Common concurrency patterns.

Four named patterns you will reach for again and again in real systems:

1. **Fan-out / fan-in**     (gather)
2. **Worker pool**           (queue + workers)
3. **Pipeline / stages**     (queue between stages)
4. **Bulkhead**              (separate semaphores per upstream)

The "AI batching" use case at the end is a preview of chapter 24.

Run:
    uvicorn 15_concurrency_patterns.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import random
import time

from fastapi import FastAPI

app = FastAPI(title="Chapter 15 — Concurrency Patterns")


async def upstream(name: str, item: int) -> dict:
    await asyncio.sleep(random.uniform(0.05, 0.2))
    return {"upstream": name, "item": item}


# --- 1. Fan-out / fan-in -----------------------------------------------------
@app.get("/fanout/{n}")
async def fanout(n: int) -> dict:
    t = time.perf_counter()
    results = await asyncio.gather(*(upstream("A", i) for i in range(n)))
    return {"count": len(results), "ms": int((time.perf_counter() - t) * 1000)}


# --- 2. Worker pool ----------------------------------------------------------
@app.get("/pool/{n}")
async def pool(n: int, workers: int = 5) -> dict:
    """Fixed worker pool pulling from one queue. Constant memory."""
    q: asyncio.Queue[int | None] = asyncio.Queue()
    done = []

    async def worker(_id: int):
        while True:
            item = await q.get()
            if item is None:
                q.task_done()
                return
            done.append(await upstream(f"w{_id}", item))
            q.task_done()

    t = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(worker(i)) for i in range(workers)]
        for i in range(n):
            await q.put(i)
        for _ in range(workers):
            await q.put(None)
    return {"workers": workers, "count": len(done), "ms": int((time.perf_counter() - t) * 1000)}


# --- 3. Pipeline / stages ----------------------------------------------------
@app.get("/pipeline/{n}")
async def pipeline(n: int) -> dict:
    """
    Stage A produces ints. Stage B doubles them. Stage C sums.
    Queues between stages let each stage progress at its own pace.
    """
    qa: asyncio.Queue = asyncio.Queue(maxsize=10)
    qb: asyncio.Queue = asyncio.Queue(maxsize=10)
    total = 0

    async def produce():
        for i in range(n):
            await qa.put(i)
        await qa.put(None)

    async def double():
        while True:
            x = await qa.get()
            if x is None:
                await qb.put(None)
                return
            await asyncio.sleep(0.01)  # imagine some work
            await qb.put(x * 2)

    async def consume():
        nonlocal total
        while True:
            x = await qb.get()
            if x is None:
                return
            total += x

    t = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(produce())
        tg.create_task(double())
        tg.create_task(consume())
    return {"sum": total, "ms": int((time.perf_counter() - t) * 1000)}


# --- 4. Bulkhead -------------------------------------------------------------
# Each upstream has its own limit. A spike to one upstream cannot starve the others.
SEM_OPENAI = asyncio.Semaphore(3)
SEM_DB = asyncio.Semaphore(10)


@app.get("/bulkhead")
async def bulkhead() -> dict:
    async def via_openai(i):
        async with SEM_OPENAI:
            return await upstream("openai", i)

    async def via_db(i):
        async with SEM_DB:
            return await upstream("db", i)

    t = time.perf_counter()
    a, b = await asyncio.gather(
        asyncio.gather(*(via_openai(i) for i in range(20))),
        asyncio.gather(*(via_db(i) for i in range(20))),
    )
    return {"openai_n": len(a), "db_n": len(b), "ms": int((time.perf_counter() - t) * 1000)}


# --- Preview: micro-batching for AI -----------------------------------------
@app.get("/batched/{n}")
async def batched(n: int, batch: int = 5) -> dict:
    """
    Collect items into batches of `batch`, send each batch in one upstream call.
    Reduces per-call overhead — the bread-and-butter optimisation for AI APIs.
    """
    async def call_batch(items: list[int]) -> list[dict]:
        await asyncio.sleep(0.1)  # one call regardless of batch size
        return [{"item": i, "y": i * i} for i in items]

    items = list(range(n))
    chunks = [items[i:i + batch] for i in range(0, len(items), batch)]
    t = time.perf_counter()
    results = await asyncio.gather(*(call_batch(c) for c in chunks))
    return {
        "items": n,
        "batches": len(chunks),
        "ms": int((time.perf_counter() - t) * 1000),
    }
