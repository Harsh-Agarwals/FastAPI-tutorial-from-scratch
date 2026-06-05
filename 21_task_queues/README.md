# 21 — Task Queues

A real queue solves what chapter 9's `BackgroundTasks` cannot:

- **Durability** — jobs survive restarts.
- **Horizontal scale** — many worker processes / machines.
- **Retries + DLQ** — bad jobs don't ruin the queue.
- **Concurrency control** — bound workers per host.

You'll meet **Celery / RQ / Dramatiq / Arq** in real codebases. They
all wrap the same primitives we build here in ~100 lines.

## Architecture

```
        ┌──────────────┐  RPUSH   ┌────────────────┐  BLPOP   ┌────────────┐
client─▶│  FastAPI app │ ───────▶ │ Redis list "Q" │ ───────▶ │ worker(s)  │
        └──────────────┘          └────────────────┘          └────────────┘
                                    │  (on failure & retries exhausted)    │
                                    ▼                                      │
                              ┌────────────┐                               │
                              │   DLQ      │ ◀─────────────────────────────┘
                              └────────────┘
```

## Run

```bash
docker run -d --name redis -p 6379:6379 redis:7

# Terminal 1
uvicorn 21_task_queues.app:app --reload --port 8000

# Terminal 2 (one or more workers)
python -m 21_task_queues.worker

# Terminal 3 — submit a few jobs
for i in {1..5}; do
  curl -s -X POST http://localhost:8000/jobs \
    -H 'Content-Type: application/json' \
    -d "{\"text\":\"job $i\"}"; echo
done
```

Watch the worker logs. The fake work fails 30% of the time, so you'll
see retries. After 3 attempts, jobs go to the DLQ.

Inspect:

```bash
curl http://localhost:8000/queue/depth
curl http://localhost:8000/jobs/<job_id>
curl -X POST http://localhost:8000/queue/replay-dlq
```

## Why BLPOP?

`BLPOP key timeout` blocks the worker until something is in the queue.
No busy-polling. Use a small timeout (1-5s) so workers can exit
cleanly on SIGTERM during deploys.

## Retries with backoff

We re-enqueue the job after `2^attempts` seconds. For correctness in
production, prefer a **delayed queue** (sorted set scored by run_at)
instead of `sleep` inside the worker — sleeping holds a connection.

## DLQ design

When a job exhausts retries:

- write it to a *separate* queue,
- alert humans (Slack, PagerDuty),
- expose a `/replay-dlq` endpoint to retry once the bug is fixed.

## When to use Celery / RQ / Dramatiq

Once your code looks like our `worker.py`, you have *invented* a worse
Celery. Switch to a library when you need:

- scheduled / cron-like jobs
- task chaining and groups
- per-queue priority
- richer monitoring (Flower etc.)

## Exercises

1. Add a `priority` field to `EnqueueIn`. Use **two** queues:
   `summarize:high` and `summarize:low`. Workers pop from high first.
2. Replace `sleep(backoff)` with a delayed-job queue using a Redis
   sorted set scored by run_at.
3. Add Prometheus counters: `jobs_enqueued`, `jobs_completed`,
   `jobs_dlq`. Expose them at `/metrics`.
