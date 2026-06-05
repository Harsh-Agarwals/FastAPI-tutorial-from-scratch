# Notes — Chapter 11

## `gather` vs `as_completed` vs `TaskGroup`

- `gather` — wait for *all*, in original order. Simple.
- `as_completed` — yields tasks as they finish; useful for streaming.
- `TaskGroup` — preferred for new code. Cleanest cancellation semantics.

## Cancellation is a normal exception

Inside a coroutine, cancellation manifests as `asyncio.CancelledError`.
Don't catch it carelessly — re-raise so the cancel propagates.

```python
try:
    await long()
except asyncio.CancelledError:
    # do quick cleanup
    raise
```

## Common gotcha: forgetting to drain a queue

`q.put(...)` is non-blocking when the queue has space. Forgetting to
`await q.get()` somewhere leaks memory. Use `maxsize` to fail fast.

## Backpressure pattern

```python
q = asyncio.Queue(maxsize=20)
await q.put(item)   # blocks if queue is full → producer slows down
```

That single line is **80% of backpressure** in production pipelines.
