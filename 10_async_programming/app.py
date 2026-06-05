"""
Chapter 10 — Async Programming, the FastAPI way.

This is the most important chapter for AI backends. The patterns
here decide whether your service can handle 10 RPS or 10,000.

Mental model:
- A single Python process runs **one event loop**.
- `async def` functions are *cooperative*: they only yield when they `await`.
- `await some_io()` parks the coroutine; the loop runs other work meanwhile.
- A `time.sleep(...)` in an `async def` is a disaster: blocks **everyone**.
- For CPU work, offload to a thread / process pool (chapters 12-14).

We side-by-side time:
  - sequential async calls
  - concurrent async calls with asyncio.gather
  - sync calls (run_in_threadpool)
  - a deliberately blocking endpoint to show the cost.

Run:
    uvicorn 10_async_programming.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import time

import httpx
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

app = FastAPI(title="Chapter 10 — Async Programming")

# A slow, mockable external service.
# httpbin.org or our own /sleep/{ms} endpoint below — both work.
EXTERNAL = "http://localhost:8000/sleep/200"


@app.get("/sleep/{ms}")
async def sleep_endpoint(ms: int) -> dict:
    """A trivial slow endpoint used as the "external" service in demos."""
    await asyncio.sleep(ms / 1000)
    return {"slept_ms": ms}


# ---- Sequential async: each await blocks the next ----
@app.get("/seq")
async def sequential() -> dict:
    t = time.perf_counter()
    async with httpx.AsyncClient(timeout=5) as client:
        for _ in range(5):
            r = await client.get(EXTERNAL)
            r.raise_for_status()
    return {"strategy": "sequential", "ms": int((time.perf_counter() - t) * 1000)}


# ---- Concurrent async: asyncio.gather overlaps all 5 calls ----
@app.get("/concurrent")
async def concurrent() -> dict:
    t = time.perf_counter()
    async with httpx.AsyncClient(timeout=5) as client:
        await asyncio.gather(*(client.get(EXTERNAL) for _ in range(5)))
    return {"strategy": "asyncio.gather", "ms": int((time.perf_counter() - t) * 1000)}


# ---- Sync handler — FastAPI auto-runs it in a threadpool so it does NOT
# block the loop. Useful for legacy / sync libraries.
import httpx as _httpx_sync  # alias just to be explicit
@app.get("/threadpool-sync")
def threadpool_sync() -> dict:
    t = time.perf_counter()
    with _httpx_sync.Client(timeout=5) as client:
        for _ in range(5):
            client.get(EXTERNAL)
    return {"strategy": "sync handler (auto threadpool)", "ms": int((time.perf_counter() - t) * 1000)}


# ---- The footgun: BLOCKING sleep inside an async handler ----
# Don't do this. We expose it ONLY to demonstrate the damage in the notebook.
@app.get("/blocking-sleep")
async def blocking_sleep() -> dict:
    time.sleep(1)  # halts the entire event loop. Bad. Bad.
    return {"strategy": "blocking sleep — entire loop frozen"}


# ---- The fix: offload sync work to a threadpool ----
def cpu_or_sync_lib(ms: int) -> int:
    time.sleep(ms / 1000)  # pretend this is `pdfminer.parse(file)` etc.
    return ms


@app.get("/offload/{ms}")
async def offloaded(ms: int) -> dict:
    t = time.perf_counter()
    # `run_in_threadpool` puts the blocking call on a worker thread so
    # the event loop keeps serving other requests.
    res = await run_in_threadpool(cpu_or_sync_lib, ms)
    return {"strategy": "run_in_threadpool", "result": res, "ms": int((time.perf_counter() - t) * 1000)}
