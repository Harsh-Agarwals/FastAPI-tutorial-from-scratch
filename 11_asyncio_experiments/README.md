# 11 — Asyncio experiments

Five patterns you will reach for again and again.

## Pattern 1 — `gather` (fan-out / fan-in)

Run many coroutines, wait for all, collect results. Linear scaling
until you saturate the upstream.

```python
results = await asyncio.gather(*(call(i) for i in range(N)))
```

If **any** coroutine raises, `gather` re-raises and the others may
still be running (unless you set `return_exceptions=True`).

## Pattern 2 — `Semaphore` (cap concurrency)

You almost never want unbounded fan-out. Real upstreams (OpenAI,
Postgres, your own services) have rate limits and connection caps.

```python
sem = asyncio.Semaphore(5)
async def guarded(i):
    async with sem:
        return await call(i)
```

Five in-flight at most, regardless of how many you spawn.

## Pattern 3 — `timeout` (always set one)

The thing that takes 5 minutes once will take 5 minutes for *every*
client until you OOM. Always bound it.

```python
async with asyncio.timeout(0.5):     # Python 3.11+
    await call()
```

For older Python: `await asyncio.wait_for(call(), timeout=0.5)`.

## Pattern 4 — Cancellation + TaskGroup

`TaskGroup` (3.11+) is the safe primitive for structured concurrency.
If any child raises, **all siblings are cancelled** and exceptions
are wrapped in an `ExceptionGroup`. No more "orphan tasks".

```python
async with asyncio.TaskGroup() as tg:
    a = tg.create_task(call(1))
    b = tg.create_task(call(2))
# both completed cleanly here, or both cancelled.
```

## Pattern 5 — `asyncio.Queue` (producer/consumer)

Decouple a fast producer from slow consumers. Apply backpressure with
`maxsize=...`. This is the *exact* shape we use for parallel PDF
summarization in chapter 28.

## Run

```bash
uvicorn 11_asyncio_experiments.app:app --reload --port 8000

curl http://localhost:8000/gather/10           # ~250ms (10 in parallel)
curl http://localhost:8000/semaphore/10        # ~500ms (cap 5, two waves)
curl http://localhost:8000/queue/12            # 3 consumers, 12 items
curl http://localhost:8000/timeout/100         # ok
curl -i http://localhost:8000/timeout/700      # 504
```

## Exercises

1. Change `gather` to set `return_exceptions=True`. Pass one task a
   sleep that raises; collect successes and failures separately.
2. Replace the `Semaphore` with `asyncio.Queue` and a fixed worker
   pool. Same effect, different shape — which is clearer?
3. Make the producer/consumer pattern **lossy**: if the queue is full
   for too long, drop new items.
