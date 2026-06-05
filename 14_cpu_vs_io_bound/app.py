"""
Chapter 14 — CPU-bound vs IO-bound — the showdown.

Same workload, four execution strategies:
  1. sync sequential
  2. async (asyncio.gather)
  3. threads (ThreadPoolExecutor)
  4. processes (ProcessPoolExecutor)

Across three workload kinds:
  a. IO sleep (perfect proxy for slow network)
  b. CPU-heavy pure Python
  c. Fake "PDF parse" (mostly CPU, a little IO)

You will see exactly which combination wins for which workload.

Run:
    uvicorn 14_cpu_vs_io_bound.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI

CORES = os.cpu_count() or 2


# --- Workloads ----------------------------------------------------------------
def io_work(ms: int = 200) -> int:
    time.sleep(ms / 1000)
    return ms


def cpu_work(n: int = 60_000) -> int:
    total = 0
    for i in range(2, n):
        if all(i % p for p in range(2, int(math.isqrt(i)) + 1)):
            total += i
    return total


def pdf_like(_: int = 0) -> int:
    """Pretend to load a small file and then parse text — small IO + CPU."""
    time.sleep(0.02)
    return cpu_work(20_000)


WORKLOADS = {"io": io_work, "cpu": cpu_work, "pdf": pdf_like}


# --- Lifespan pools -----------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tpool = ThreadPoolExecutor(max_workers=CORES * 4)
    app.state.ppool = ProcessPoolExecutor(max_workers=CORES)
    try:
        yield
    finally:
        app.state.tpool.shutdown(wait=True, cancel_futures=True)
        app.state.ppool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title="Chapter 14 — CPU vs IO benchmarks", lifespan=lifespan)


# --- Helpers ------------------------------------------------------------------
def _ms(t: float) -> int:
    return int((time.perf_counter() - t) * 1000)


async def run_async(fn, n: int) -> int:
    """For IO-only: gather native coroutines that wrap a sync sleep."""
    async def _one():
        await asyncio.sleep(0.2 if fn is io_work else 0)
        if fn is not io_work:
            fn()
    t = time.perf_counter()
    await asyncio.gather(*(_one() for _ in range(n)))
    return _ms(t)


async def run_threads(fn, n: int) -> int:
    loop = asyncio.get_running_loop()
    t = time.perf_counter()
    await asyncio.gather(*(loop.run_in_executor(app.state.tpool, fn) for _ in range(n)))
    return _ms(t)


async def run_procs(fn, n: int) -> int:
    loop = asyncio.get_running_loop()
    t = time.perf_counter()
    await asyncio.gather(*(loop.run_in_executor(app.state.ppool, fn) for _ in range(n)))
    return _ms(t)


def run_sync(fn, n: int) -> int:
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return _ms(t)


# --- Routes -------------------------------------------------------------------
@app.get("/benchmark/{kind}")
async def benchmark(kind: str, n: int = 8) -> dict:
    if kind not in WORKLOADS:
        return {"error": "kind must be one of io / cpu / pdf"}
    fn = WORKLOADS[kind]

    return {
        "kind": kind,
        "n": n,
        "cores": CORES,
        "results_ms": {
            "sync_sequential": run_sync(fn, n),
            "async_gather": await run_async(fn, n),
            "threads": await run_threads(fn, n),
            "processes": await run_procs(fn, n),
        },
    }
