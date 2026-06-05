"""
Chapter 12 — Threading in a FastAPI world.

Threads in CPython share the GIL. That means:
- Threading helps for **IO-bound** work (waiting on disk/network).
- Threading does NOT help (much) for **CPU-bound** work — use processes.

Common uses in a FastAPI app:
- Wrapping a synchronous library you can't replace (e.g. PyPDF for very
  small docs, blocking SDKs).
- Running short blocking calls without freezing the event loop.

We compare:
  - Single-thread sequential
  - ThreadPoolExecutor for IO
  - ThreadPoolExecutor for CPU (and see why it's not better)

Run:
    uvicorn 12_threading.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI

app = FastAPI(title="Chapter 12 — Threading")


# A blocking IO-bound function (mimics a slow sync HTTP / disk call).
def io_task(ms: int) -> int:
    time.sleep(ms / 1000)
    return ms


# A CPU-bound function (no IO, real arithmetic).
def cpu_task(n: int) -> int:
    # sum of primes up to n — burns CPU.
    total = 0
    for i in range(2, n):
        if all(i % p for p in range(2, int(math.isqrt(i)) + 1)):
            total += i
    return total


# ---- IO-bound: threads DO help ----
@app.get("/io/sequential/{n}")
async def io_seq(n: int) -> dict:
    t = time.perf_counter()
    for _ in range(n):
        io_task(100)
    return {"ms": int((time.perf_counter() - t) * 1000)}


@app.get("/io/threaded/{n}")
async def io_thr(n: int, workers: int = 8) -> dict:
    """Offload to a thread pool. The event loop stays free for other clients."""
    t = time.perf_counter()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        await asyncio.gather(*(loop.run_in_executor(pool, io_task, 100) for _ in range(n)))
    return {"ms": int((time.perf_counter() - t) * 1000), "workers": workers}


# ---- CPU-bound: threads do NOT help (GIL) ----
@app.get("/cpu/sequential/{n}")
async def cpu_seq(n: int) -> dict:
    t = time.perf_counter()
    for _ in range(n):
        cpu_task(50_000)
    return {"ms": int((time.perf_counter() - t) * 1000)}


@app.get("/cpu/threaded/{n}")
async def cpu_thr(n: int, workers: int = 8) -> dict:
    """Same total work, but split across threads. Expect minimal speedup."""
    t = time.perf_counter()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        await asyncio.gather(*(loop.run_in_executor(pool, cpu_task, 50_000) for _ in range(n)))
    return {"ms": int((time.perf_counter() - t) * 1000), "workers": workers}


# ---- Thread safety demo ----
_unsafe_counter = 0
_safe_counter = 0
_lock = threading.Lock()


def _race():
    """Run on many threads — race condition is observable."""
    global _unsafe_counter, _safe_counter
    for _ in range(100_000):
        _unsafe_counter += 1                # NOT atomic in general
        with _lock:
            _safe_counter += 1


@app.get("/race")
async def race() -> dict:
    global _unsafe_counter, _safe_counter
    _unsafe_counter = 0
    _safe_counter = 0
    threads = [threading.Thread(target=_race) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return {
        "expected": 8 * 100_000,
        "unsafe_counter": _unsafe_counter,  # often less than expected
        "safe_counter": _safe_counter,
    }
