# 10 — Async Programming (the chapter that pays for itself)

This is **the** chapter. Everything in the AI half of this repo
depends on understanding the event loop.

## One paragraph mental model

A FastAPI / uvicorn worker runs **one event loop** in **one thread**.
`async def` functions are *coroutines*: they can pause themselves on
`await` so the loop can do other work. They never preempt each other —
they cooperate. If a coroutine **never yields** (because it runs CPU
or calls a blocking library), the loop is frozen. Nothing else runs.

## Rules of thumb

1. **For IO** (HTTP, DB, disk, Redis) — use `async def` + async libs
   (`httpx`, `aiofiles`, `redis.asyncio`, `asyncpg`/SQLAlchemy async).
2. **For CPU-heavy work** — offload to a **process pool**, never run
   it in the loop or a thread (GIL).
3. **For sync libraries you can't replace** — offload to a thread via
   `run_in_threadpool(...)`.
4. **`time.sleep(...)` in async code is illegal.** Use `asyncio.sleep`.

## Run + time the demos

Open two terminals.

```bash
# Terminal A
uvicorn 10_async_programming.app:app --reload --port 8000

# Terminal B
curl http://localhost:8000/seq          # ~1000+ ms (5 × 200ms serial)
curl http://localhost:8000/concurrent   # ~200 ms (5 in parallel)
curl http://localhost:8000/threadpool-sync   # similar to seq — each call blocks one thread
curl http://localhost:8000/offload/500  # ~500ms, doesn't freeze others
```

While `/blocking-sleep` is running for 1 second, **all** other requests
to the worker stall. Try hitting `/concurrent` at the same time.

## Why concurrent beats sequential here

`asyncio.gather` lets all 5 HTTP calls overlap. While one is waiting
for bytes from the network, the loop is freely starting / advancing
the other 4. Sequential `await` only progresses one at a time.

## When sync handlers are fine

Defining a handler as `def` (not `async def`) tells FastAPI to run it
in a threadpool. Good escape hatch for:

- legacy sync ORMs (e.g., synchronous SQLAlchemy 1.x)
- CPU-light libraries that block on file/network IO

But: every thread is one open socket / DB connection. Don't make this
the default for high-RPS endpoints.

## Common mistakes

- Awaiting a `requests.get(...)` — `requests` is sync; you blocked the loop.
- Calling `model.predict()` inside an async handler — CPU stalls the loop.
- Forgetting to `await` on a coroutine — runtime warning, function never runs.
- Sharing an `httpx.AsyncClient` *across* requests but creating it on every
  request — wasteful. Create once via a yield-dep (chapter 4).

## Production patterns we will revisit

- One reusable `httpx.AsyncClient` per worker (DI).
- A shared semaphore to cap concurrency to upstream APIs.
- Timeouts at **every** layer.
- A `ProcessPoolExecutor` for PDF parsing (chapter 13).

## Exercises

1. Change `gather` to `asyncio.as_completed` and print results as they
   finish. When is that better?
2. Add a 100 ms upstream timeout via `httpx.Timeout` and observe what
   happens when downstream takes 200 ms.
3. Replace `time.sleep` in `/blocking-sleep` with `await asyncio.sleep(1)`.
   Confirm the freeze goes away.
