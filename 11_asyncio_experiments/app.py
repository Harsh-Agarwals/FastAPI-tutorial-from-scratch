"""
Chapter 11 — asyncio playground inside a FastAPI app.

Patterns covered:
- asyncio.gather (fan-out / fan-in)
- asyncio.create_task (named tasks)
- Semaphore (cap upstream concurrency)
- Timeout (asyncio.timeout in 3.11+)
- Cancellation propagation
- Producer / consumer with asyncio.Queue

These patterns will appear again in chapters 24 (AI batching) and 28
(parallel PDF summarization).

Run:
    uvicorn 11_asyncio_experiments.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import random
import time

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Chapter 11 — Asyncio Experiments")


# -- An imaginary slow downstream service ---------------------------------
async def slow_call(idx: int, base_ms: int = 200) -> dict:
    jitter = random.randint(0, 100)
    await asyncio.sleep((base_ms + jitter) / 1000)
    return {"idx": idx, "ms": base_ms + jitter}


# -- gather: classic fan-out / fan-in --------------------------------------
@app.get("/gather/{n}")
async def gather_n(n: int) -> dict:
    if n > 50:
        raise HTTPException(400, "Pick n <= 50")
    t = time.perf_counter()
    results = await asyncio.gather(*(slow_call(i) for i in range(n)))
    return {"results": results, "ms": int((time.perf_counter() - t) * 1000)}


# -- Semaphore: cap concurrency to e.g. 5 to be nice to upstreams ----------
@app.get("/semaphore/{n}")
async def with_semaphore(n: int, max_concurrent: int = 5) -> dict:
    sem = asyncio.Semaphore(max_concurrent)

    async def guarded(i):
        async with sem:  # only `max_concurrent` of these run at once.
            return await slow_call(i)

    t = time.perf_counter()
    results = await asyncio.gather(*(guarded(i) for i in range(n)))
    return {
        "max_concurrent": max_concurrent,
        "results_count": len(results),
        "ms": int((time.perf_counter() - t) * 1000),
    }


# -- Timeout: bound the worst case ----------------------------------------
@app.get("/timeout/{ms}")
async def with_timeout(ms: int) -> dict:
    try:
        # Python 3.11+ syntax. Pre-3.11: asyncio.wait_for(...).
        async with asyncio.timeout(0.5):
            return await slow_call(0, base_ms=ms)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Upstream took too long (>500ms)")


# -- Cancellation: when the client disconnects, child tasks must die too ---
@app.get("/cancel-demo")
async def cancel_demo() -> dict:
    # We start 3 long tasks. If client disconnects mid-flight, FastAPI cancels
    # the handler coroutine, which cascades the cancellation to child tasks
    # — *if* you `await` them or wrap them in a TaskGroup (3.11+).
    async with asyncio.TaskGroup() as tg:
        a = tg.create_task(slow_call(1, 800))
        b = tg.create_task(slow_call(2, 800))
        c = tg.create_task(slow_call(3, 800))
    return {"a": a.result(), "b": b.result(), "c": c.result()}


# -- Producer / consumer with asyncio.Queue --------------------------------
@app.get("/queue/{n}")
async def queue_demo(n: int) -> dict:
    """
    Single producer pushes N items. Three consumers pull in parallel.
    Mirrors a real pipeline: read PDF chunks (producer), summarize (consumers).
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    results: list[dict] = []

    async def producer():
        for i in range(n):
            await q.put(i)
        # Sentinels tell consumers to stop.
        for _ in range(3):
            await q.put(None)

    async def consumer(name: str):
        while True:
            item = await q.get()
            try:
                if item is None:
                    return
                results.append({"by": name, **(await slow_call(item, 100))})
            finally:
                q.task_done()

    t = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer())
        for nm in ("c1", "c2", "c3"):
            tg.create_task(consumer(nm))

    return {
        "results_count": len(results),
        "by_worker": {k: sum(1 for r in results if r["by"] == k) for k in ("c1", "c2", "c3")},
        "ms": int((time.perf_counter() - t) * 1000),
    }
