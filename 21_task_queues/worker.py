"""
A minimal worker process. Run multiple instances for horizontal scale:
    python -m 21_task_queues.worker
    python -m 21_task_queues.worker  # in another terminal — they share work
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import signal
import time

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = "queue:summarize"
DLQ = "queue:summarize:dlq"
STATE_PREFIX = "job:"
MAX_RETRIES = 3

_should_stop = False


def _on_signal(*_):
    global _should_stop
    _should_stop = True


async def update(r, job_id: str, **fields):
    await r.hset(STATE_PREFIX + job_id, mapping={k: json.dumps(v) for k, v in fields.items()})


async def fake_work(text: str) -> str:
    """Pretend to call an LLM. Fail randomly 30% of the time so retries fire."""
    await asyncio.sleep(0.5)
    if random.random() < 0.3:
        raise RuntimeError("flaky upstream")
    return text[:40] + ("…" if len(text) > 40 else "")


async def process_one(r, raw: str) -> None:
    item = json.loads(raw)
    job_id = item["id"]
    state = await r.hgetall(STATE_PREFIX + job_id)
    job = {k: json.loads(v) for k, v in state.items()}
    job["attempts"] = int(job.get("attempts", 0)) + 1

    await update(r, job_id, status="running", attempts=job["attempts"], started_at=time.time())
    try:
        result = await fake_work(job["text"])
        await update(r, job_id, status="done", result=result, finished_at=time.time())
        print(f"[worker] done {job_id} attempt={job['attempts']}")
    except Exception as e:  # noqa: BLE001
        if job["attempts"] >= MAX_RETRIES:
            await update(r, job_id, status="failed", error=str(e), finished_at=time.time())
            await r.rpush(DLQ, raw)
            print(f"[worker] DLQ  {job_id} after {job['attempts']} attempts: {e}")
        else:
            # Exponential backoff. In production you would use a delayed queue.
            backoff_s = min(30, 2 ** job["attempts"])
            await update(r, job_id, status="retrying", error=str(e))
            print(f"[worker] retry {job_id} in {backoff_s}s (attempt {job['attempts']}): {e}")
            await asyncio.sleep(backoff_s)
            await r.rpush(QUEUE, raw)


async def main() -> None:
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    print("[worker] up, polling", QUEUE)
    while not _should_stop:
        # BLPOP blocks until something is available (or timeout).
        popped = await r.blpop(QUEUE, timeout=2)
        if popped is None:
            continue
        _key, raw = popped
        try:
            await process_one(r, raw)
        except Exception:
            # Last-resort: if process_one itself crashes, requeue.
            print("[worker] process_one crashed; requeue")
            await r.rpush(QUEUE, raw)
    await r.close()
    print("[worker] bye")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)
    asyncio.run(main())
