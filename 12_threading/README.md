# 12 — Threading

Threading is the right tool when:

- you need to call a **blocking sync** library from async code
- the work is **IO-bound** (network, disk, sleep)

It is the **wrong tool** when the work is CPU-heavy. The GIL means only
one Python bytecode thread runs at a time. Use processes for CPU work
(chapter 13).

## Run + benchmark

```bash
uvicorn 12_threading.app:app --reload --port 8000

curl http://localhost:8000/io/sequential/10     # ~1000ms
curl http://localhost:8000/io/threaded/10       # ~150ms — clear win

curl http://localhost:8000/cpu/sequential/4     # baseline
curl http://localhost:8000/cpu/threaded/4       # similar (GIL!)

curl http://localhost:8000/race                 # see the unsafe vs safe counter
```

## When threads help (IO)

`time.sleep(0.1)` releases the GIL while sleeping. So do `socket.recv`,
`open(...).read()`, `requests.get(...)`. Other threads make progress
while one is parked.

## When threads don't help (CPU)

`for i in range(...): x += i` holds the GIL the entire time. Splitting
across threads adds overhead without parallelism. Use `ProcessPoolExecutor`.

## Thread safety in 60 seconds

Anything you write to from multiple threads needs **synchronisation**.
`+= 1` on an int is read-modify-write — three bytecodes — and may be
preempted. Use `threading.Lock` (or `queue.Queue`, which is safe).

In FastAPI specifically, your handler **state** should be per-request
(or via a thread-safe lib like Redis), not module-level mutables.

## The escape hatch in async FastAPI

```python
from fastapi.concurrency import run_in_threadpool
result = await run_in_threadpool(sync_lib_call, arg)
```

That's how you safely call sync libs from `async def` handlers.

## Exercises

1. Benchmark different `workers=` values on `/io/threaded/100`. Where
   does the curve flatten? Why?
2. Replace `time.sleep` in `io_task` with a `httpx.Client().get(...)`
   to a localhost slow endpoint. Same shape, real IO.
3. Make `cpu_task` release the GIL by calling into NumPy (which uses
   C threads). Re-benchmark the threaded version. Surprise!
