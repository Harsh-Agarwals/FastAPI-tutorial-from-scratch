# Notes — Chapter 10

## What "blocking" really means

The event loop is a `while True:` loop that pops "ready" callbacks
and runs them to the next `await`. If your callback never yields,
the while-loop is stuck. That is **blocking**.

## How to find blocking code in production

- Enable `PYTHONASYNCIODEBUG=1` in dev — warns on slow callbacks.
- Use `aiomonitor` to inspect tasks.
- Look at p99 latency under load — a single bad endpoint will spike
  *every* endpoint's tail latency.

## httpx vs aiohttp vs requests

| Library  | Sync? | Async? | Streaming? | Notes                          |
|----------|-------|--------|------------|--------------------------------|
| requests | ✓     | ✗      | limited    | The classic. Never in async.   |
| aiohttp  | ✗     | ✓      | ✓          | Older async API.               |
| httpx    | ✓     | ✓      | ✓          | One library, both modes. 👍     |

We use `httpx` throughout.

## anyio is everywhere

FastAPI uses `anyio` under the hood; `run_in_threadpool` calls into
`anyio.to_thread.run_sync`. If you see anyio in tracebacks — that is
where it comes from.

## Tuning the threadpool

Default threadpool size is `min(32, os.cpu_count() + 4)`. If you offload
heavily, tune via:

```python
import anyio.to_thread
limiter = anyio.to_thread.current_default_thread_limiter()
limiter.total_tokens = 100
```
