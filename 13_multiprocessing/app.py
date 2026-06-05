"""
Chapter 13 — Multiprocessing for CPU-heavy work.

`ProcessPoolExecutor` spawns **separate Python processes**, each with
their own GIL. CPU-bound work now actually runs in parallel.

Costs to be aware of:
- Process startup (~50-200 ms) — amortise with a long-lived pool.
- Arguments are *pickled* and sent over a pipe — keep them small.
- Imports run *per process* — keep workers slim, lazy-import heavy deps.

In a FastAPI app, we instantiate the pool **once** at startup and
reuse it across requests.

Run:
    uvicorn 13_multiprocessing.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Default worker count: number of CPU cores. Tune for your workload.
WORKERS = max(1, (os.cpu_count() or 2) - 1)


def cpu_task(n: int) -> int:
    """Same arithmetic as chapter 12 — sum of primes < n."""
    total = 0
    for i in range(2, n):
        if all(i % p for p in range(2, int(math.isqrt(i)) + 1)):
            total += i
    return total


# Lifespan: open the pool when the app starts, close it on shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = ProcessPoolExecutor(max_workers=WORKERS)
    try:
        yield
    finally:
        app.state.pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title="Chapter 13 — Multiprocessing", lifespan=lifespan)


@app.get("/cpu/sequential/{n}")
async def cpu_seq(n: int) -> dict:
    t = time.perf_counter()
    for _ in range(n):
        cpu_task(50_000)
    return {"strategy": "sequential", "ms": int((time.perf_counter() - t) * 1000)}


@app.get("/cpu/processes/{n}")
async def cpu_proc(n: int) -> dict:
    t = time.perf_counter()
    loop = asyncio.get_running_loop()
    pool: ProcessPoolExecutor = app.state.pool
    await asyncio.gather(*(loop.run_in_executor(pool, cpu_task, 50_000) for _ in range(n)))
    return {
        "strategy": "process pool",
        "workers": WORKERS,
        "ms": int((time.perf_counter() - t) * 1000),
    }
