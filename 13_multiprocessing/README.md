# 13 — Multiprocessing (for CPU)

Threads can't beat the GIL on pure-Python CPU. Processes can —
each gets its own interpreter.

## When to reach for processes

- Heavy text / numeric Python (PDF parsing, regex over MB of text)
- Image processing without C extensions
- ML inference in pure Python (rare; usually delegated to a model server)

## When **not** to

- IO-bound work (use async or threads)
- Tiny tasks (pickle + spawn overhead can dominate)
- Crossing process boundaries with huge args (the pipe becomes the bottleneck)

## Run

```bash
uvicorn 13_multiprocessing.app:app --reload --port 8000

curl http://localhost:8000/cpu/sequential/4    # baseline
curl http://localhost:8000/cpu/processes/4     # near 4x faster on 4 cores
curl http://localhost:8000/cpu/processes/8     # diminishing returns past N=cores
```

## Lifespan-managed pool

We open the pool **once** in the FastAPI `lifespan` context. Reusing
the same pool across requests amortises the worker startup cost.

```python
@asynccontextmanager
async def lifespan(app):
    app.state.pool = ProcessPoolExecutor(max_workers=N)
    yield
    app.state.pool.shutdown()
```

## Pitfalls

- **Closures don't pickle.** Top-level functions only.
- **Be explicit about what you send.** Big inputs over the pipe are slow.
- **On macOS / Windows, spawn is the default start method.** Code at
  import time runs in every worker — keep it cheap.
- **OOM kills.** Each worker is a full process. Profile memory.

## Exercises

1. Switch the pool to `loky` (used by joblib) or `dask` — what changes?
2. Use `pool.map(fn, items, chunksize=8)` to batch — when does that win?
3. Measure pickle overhead: pass a 50 MB numpy array as arg vs writing
   it to `/dev/shm` and passing a path.
