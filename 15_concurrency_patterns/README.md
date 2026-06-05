# 15 — Concurrency patterns (a small toolbox)

Four shapes solve 90% of real concurrency problems. Learn the names —
your future self will thank you in design reviews.

## 1. Fan-out / fan-in

Run N independent tasks, collect all results.

```python
results = await asyncio.gather(*(call(i) for i in range(N)))
```

Pros: simple. Cons: unbounded concurrency unless you add a semaphore.

## 2. Worker pool

Bounded set of consumers reading from a queue. Constant memory, easy
backpressure. We use it for parallel PDF chunk summarisation.

```python
async def worker():
    while True:
        x = await q.get()
        if x is None: return
        await handle(x)
```

## 3. Pipeline / stages

Producer → queue → transform → queue → consumer. Each stage runs at
its own pace; queues absorb mismatches and apply backpressure when
the downstream is slow.

```
[producer] → Q1 → [transform x N] → Q2 → [consumer]
```

## 4. Bulkhead

Different upstreams get separate concurrency budgets. A spike to one
service cannot drain the connection pool of another.

```python
SEM_OPENAI = asyncio.Semaphore(3)
SEM_DB     = asyncio.Semaphore(10)
```

Named after watertight compartments in ships — flood one, the others
stay dry.

## Bonus: micro-batching

When the upstream's per-call cost is high but per-item cost is small
(OpenAI's embeddings endpoint, vector DB inserts), batch:

```python
chunks = [items[i:i+B] for i in range(0, len(items), B)]
results = await asyncio.gather(*(call_batch(c) for c in chunks))
```

Often 5-10× cheaper *and* faster.

## Run

```bash
uvicorn 15_concurrency_patterns.app:app --reload --port 8000

curl http://localhost:8000/fanout/20
curl http://localhost:8000/pool/20?workers=5
curl http://localhost:8000/pipeline/20
curl http://localhost:8000/bulkhead
curl http://localhost:8000/batched/100?batch=10
```

## Exercises

1. Add a per-task timeout to the worker pool. What happens if a task
   exceeds it? Make sure the worker keeps processing the next item.
2. Add a metric counter to the bulkhead endpoint showing how often
   each semaphore was *full* (a hint that you need more capacity).
3. Make the pipeline lossy: if `qa` fills for more than 100ms, drop
   the oldest item.
