# Notes — Chapter 09

## `BackgroundTasks` vs `create_task` — small but important

- `BackgroundTasks` is scheduled by FastAPI **after** the response is
  written to the wire. Latency-sensitive paths benefit.
- `asyncio.create_task` runs **concurrently** with the response. If
  your task touches the same DB session as the handler, you have a race.

## Don't lose tasks!

If you call `asyncio.create_task(...)` and discard the returned task,
the event loop will warn about "Task was destroyed but it is pending!"
on shutdown. Keep a strong reference (we use `_TASKS: set[Task]`) and
remove on `done`.

## Exceptions in background tasks

`BackgroundTasks` will silently swallow exceptions unless your task
function logs them. Always `try/except/log`. Better: have a tiny
wrapper:

```python
async def with_logging(coro):
    try:
        await coro
    except Exception:
        log.exception("background task failed")
```

## Why polling first, websockets later?

Polling is robust, simple, and stateless. It scales linearly with
clients × poll-rate. Websockets are great for *streaming progress* —
we will use them for the AI summary stream in chapter 16.
