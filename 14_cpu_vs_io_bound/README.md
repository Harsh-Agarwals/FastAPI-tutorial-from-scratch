# 14 — CPU-bound vs IO-bound — the showdown

We benchmark the *same* workload under four strategies. The numbers
will make the trade-offs unforgettable.

## Run

```bash
uvicorn 14_cpu_vs_io_bound.app:app --reload --port 8000

curl -s 'http://localhost:8000/benchmark/io?n=8'  | jq
curl -s 'http://localhost:8000/benchmark/cpu?n=8' | jq
curl -s 'http://localhost:8000/benchmark/pdf?n=8' | jq
```

You should see something close to (numbers vary by machine):

| Strategy   | IO (8 × 200ms) | CPU (8 × 60k) | PDF-like |
|------------|---------------:|--------------:|---------:|
| sync       | ~1600 ms       | baseline      | slowest  |
| async      | ~200 ms        | ≈ sync (GIL)  | ≈ sync   |
| threads    | ~200 ms        | ≈ sync (GIL)  | ≈ sync   |
| processes  | ~ slower than threads for IO (overhead) | ~baseline/N | best for "pdf" |

## The decision tree

```
Is the work waiting on someone else (network / disk / sleep)?
  └─ YES → IO-bound → prefer ASYNC. Threads are an OK fallback.

Is the work pure Python doing math / parsing?
  └─ YES → CPU-bound → use PROCESSES.

Is it both?
  └─ Split: async handler dispatches → process pool for the CPU part.
```

This is the exact decision we make in the AI PDF Summarizer (chapter 29):
- Upload + queueing → async
- PDF parsing → process pool
- LLM summarization → async (it is IO from our perspective)

## Why async wins for IO

Async lets one thread juggle thousands of in-flight requests. Each
coroutine costs ~KB instead of a thread's ~MB. Less context switching.
No GIL fights.

## Why processes win for CPU

Each Python process has its own GIL. With N processes on N cores, your
program is genuinely N× faster (minus pickle / IPC overhead).

## Why threads are an OK middle for sync libs

If you must call a synchronous library that does IO (e.g., a sync DB
driver), threads let the loop keep serving other requests while one
thread waits. You give up some elegance but stay responsive.

## Exercises

1. Sweep `n` from 1 to 64. Plot the four strategies. Where does each
   curve start to flatten?
2. Replace `io_work` with a real `httpx.Client().get(...)`. Does the
   shape of the chart change?
3. Change `cpu_work` to use NumPy (`np.arange(n).sum()`). Why does
   threads suddenly help?
