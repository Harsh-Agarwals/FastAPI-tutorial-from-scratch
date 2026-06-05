# 09 — Background Tasks (the easy way)

When work takes too long for one HTTP round-trip, give the client a
**job id** and let them poll. This chapter shows the simplest pattern
that still feels professional.

## Two in-process options

| Option                       | When to use                                       |
|------------------------------|---------------------------------------------------|
| `BackgroundTasks`            | Work runs **after** the response is sent.         |
| `asyncio.create_task`        | Work starts **immediately** in parallel.          |

Both run in the **same process** as your HTTP worker. If the worker
restarts, the job is lost. For durability, see chapter 21.

## Run

```bash
uvicorn 09_background_tasks.app:app --reload --port 8000

# Submit a job (slow 3s)
JOB=$(curl -s -X POST http://localhost:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{"text":"some long document...", "delay_s":3}' | jq -r .job_id)

# Poll until done
for i in 1 2 3 4 5 6; do
  curl -s http://localhost:8000/jobs/$JOB | jq '{status, result}'; sleep 0.7
done
```

## The 202 + Location pattern

For async work, respond with:

- HTTP **202 Accepted** ("we got it, not done yet")
- A body or `Location` header pointing at the status URL

That gives the client a stable contract and is friendly to retries.

## Polling strategy on the client

- Exponential backoff (200 ms → 400 ms → 800 ms, capped at, say, 2 s).
- Stop after some max time or on `status in {"done","failed"}`.
- For long jobs, switch to **websockets** (chapter 16) or **SSE**
  (chapter 17) to push updates instead of polling.

## Limits of in-process tasks

- Killed if the worker restarts (deploys).
- Cannot scale work across machines.
- One bad task can starve the event loop if it forgets to `await`.
- No retries, no schedules, no dead-letter queue.

When you need those, move to chapter 21 (real task queues).

## Exercises

1. Add a `cancel` endpoint that sets the job to `cancelled` *and*
   actually stops the task (hint: store the `asyncio.Task` on the
   job record, then call `.cancel()`).
2. Persist `_JOBS` to Redis instead of an in-memory dict — survives
   restarts but still in-process.
3. Add **idempotency**: clients can pass `Idempotency-Key` so two
   identical retries return the same job id.
