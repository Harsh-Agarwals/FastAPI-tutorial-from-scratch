"""
Chapter 09 — Background Tasks + Polling Patterns

Goal: respond fast, do work later, let the client check on it.

We build the smallest possible "fake AI summarizer":
  - POST /jobs       -> returns a job id (202 Accepted)
  - GET  /jobs/{id}  -> polling endpoint with status + result

Two strategies are shown:
  1. `BackgroundTasks` (in-process, single-worker)
  2. `asyncio.create_task` (also in-process — for comparison)

Both are fine for small workloads. Chapter 21 introduces real queues
(Celery / RQ / Dramatiq) for multi-worker, retry-able, durable work.

Run:
    uvicorn 09_background_tasks.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Chapter 09 — Background Tasks")

# --- In-memory job store --------------------------------------------------
JobStatus = Literal["pending", "running", "done", "failed"]


class JobIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    delay_s: float = Field(default=2.0, ge=0, le=10)  # simulate AI latency


class JobRecord(BaseModel):
    id: str
    status: JobStatus = "pending"
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: str | None = None
    error: str | None = None


_JOBS: dict[str, JobRecord] = {}


# --- The "work" — pretend it is calling an LLM ---------------------------
async def fake_summarize(job_id: str, payload: JobIn) -> None:
    job = _JOBS[job_id]
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    try:
        # Simulate IO-bound work (network call to LLM).
        await asyncio.sleep(payload.delay_s)
        # Pretend summary: first 60 chars + ellipsis.
        job.result = (payload.text[:60] + ("…" if len(payload.text) > 60 else "")).strip()
        job.status = "done"
    except Exception as e:  # noqa: BLE001
        job.error = repr(e)
        job.status = "failed"
    finally:
        job.finished_at = datetime.now(timezone.utc)


# --- Approach 1: FastAPI BackgroundTasks ---------------------------------
# Runs *after* the response is sent. Same event loop, same process.
@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(payload: JobIn, bg: BackgroundTasks) -> dict:
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = JobRecord(id=job_id, submitted_at=datetime.now(timezone.utc))
    bg.add_task(fake_summarize, job_id, payload)
    # 202 + Location header is the conventional pattern.
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


# --- Approach 2: asyncio.create_task (fire-and-forget) -------------------
# Useful when you want the task to start *immediately*, not after the
# response is sent. Be careful: nothing waits on it; uncaught exceptions
# are easy to lose. We add a done-callback to log failures.
_TASKS: set[asyncio.Task] = set()


@app.post("/jobs/now", status_code=status.HTTP_202_ACCEPTED)
async def submit_now(payload: JobIn) -> dict:
    job_id = uuid.uuid4().hex[:12]
    _JOBS[job_id] = JobRecord(id=job_id, submitted_at=datetime.now(timezone.utc))
    task = asyncio.create_task(fake_summarize(job_id, payload))

    def _on_done(t: asyncio.Task):
        _TASKS.discard(t)
        if exc := t.exception():
            # In real code this would go to your logger / alerting.
            print("task failed:", exc)

    task.add_done_callback(_on_done)
    _TASKS.add(task)
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


# --- Polling endpoint -----------------------------------------------------
@app.get("/jobs/{job_id}", response_model=JobRecord)
async def get_job(job_id: str) -> JobRecord:
    if (job := _JOBS.get(job_id)) is None:
        raise HTTPException(404, "Unknown job id")
    return job
