# Notebooks — cross-cutting experiments

Where the chapter notebooks focus on one concept each, **these
notebooks deliberately compare** across concepts. They are the lab
bench of the repository.

| Notebook                       | What it explores                              |
|--------------------------------|-----------------------------------------------|
| `01_asyncio_timing.ipynb`      | sequential vs gather vs as_completed timing   |
| `02_threading_vs_processes.ipynb`| IO and CPU benchmarks side by side          |
| `03_event_loop_visualised.ipynb`| trace tasks, see ordering                    |
| `04_ai_request_batching.ipynb` | per-call vs batched call latency / cost      |
| `05_concurrency_experiments.ipynb`| semaphores, queues, backpressure           |
| `06_cache_hit_ratios.ipynb`    | hit ratio under different access patterns     |
| `07_rate_limiter_simulator.ipynb`| visualise token bucket / sliding window     |

Run each notebook inside a Python venv with the global
`requirements.txt` installed. Some require Redis (`docker run redis`).

## Suggested order

If you have already finished the chapters, run the notebooks in the
order above. They make connections between concepts that the
chapter-by-chapter walk only hints at.
