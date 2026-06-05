"""
Chapter 29 — The capstone: AI PDF Summarizer.

This service ties every prior concept together:

  Client ──▶ POST /upload          (ch 8: validated, streamed upload)
        ◀── 202 + job_id           (ch 9: 202 + Location pattern)
        ──▶ POST /summarize/{id}   enqueues a job in Redis (ch 21)
        ──▶ GET  /jobs/{id}        polls (ch 9, ch 23 metrics)
        ──▶ WS   /jobs/{id}/stream live token progress (ch 16)

  Worker (separate process):
       reads from Redis queue
       parses PDF in process pool (ch 13)
       summarises chunks via LLM with semaphore + retry + cache (ch 11, 19, 24)
       writes progress to Redis (ch 20)
       publishes tokens on a pub/sub channel for WS (ch 16, 20)

Run:
    docker run -d --name redis -p 6379:6379 redis:7
    uvicorn 29_ai_pdf_summarizer.app:app --reload --port 8000
    python -m 29_ai_pdf_summarizer.worker
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import uuid
from contextlib import asynccontextmanager

import aiofiles
import redis.asyncio as aioredis
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
UPLOAD_DIR = pathlib.Path(os.getenv("UPLOAD_DIR", "./_uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

QUEUE = "queue:summarize_pdf"
JOB_PREFIX = "summary:job:"
CHANNEL_PREFIX = "summary:tokens:"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    await app.state.redis.ping()
    try:
        yield
    finally:
        await app.state.redis.close()


app = FastAPI(title="Chapter 29 — AI PDF Summarizer (Capstone)", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Upload — validates, streams to disk, returns a file id.
# ---------------------------------------------------------------------------
class UploadOut(BaseModel):
    file_id: str
    bytes: int


@app.post("/upload", response_model=UploadOut, status_code=201)
async def upload(file: UploadFile = File(...)) -> UploadOut:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, "Send a PDF")
    fid = uuid.uuid4().hex[:12]
    target = UPLOAD_DIR / f"{fid}.pdf"
    size = 0
    first = b""
    async with aiofiles.open(target, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            if not first:
                first = chunk[:8]
            size += len(chunk)
            if size > 20 * 1024 * 1024:
                await f.close()
                target.unlink(missing_ok=True)
                raise HTTPException(413, "PDF too large (20 MB cap)")
            await f.write(chunk)
    if not first.startswith(b"%PDF-"):
        target.unlink(missing_ok=True)
        raise HTTPException(400, "Not a PDF")
    return UploadOut(file_id=fid, bytes=size)


# ---------------------------------------------------------------------------
# Enqueue a summarisation job for a previously uploaded file.
# ---------------------------------------------------------------------------
class EnqueueOut(BaseModel):
    job_id: str
    status_url: str
    stream_url: str


@app.post("/summarize/{file_id}", response_model=EnqueueOut, status_code=202)
async def summarize(file_id: str) -> EnqueueOut:
    target = UPLOAD_DIR / f"{file_id}.pdf"
    if not target.exists():
        raise HTTPException(404, "No such file_id; upload first")

    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "file_id": file_id,
        "status": "queued",
        "chunks_total": 0,
        "chunks_done": 0,
        "summary": "",
    }
    pipe = app.state.redis.pipeline()
    pipe.hset(JOB_PREFIX + job_id, mapping={k: json.dumps(v) for k, v in job.items()})
    pipe.rpush(QUEUE, json.dumps({"job_id": job_id, "path": str(target)}))
    await pipe.execute()
    return EnqueueOut(
        job_id=job_id,
        status_url=f"/jobs/{job_id}",
        stream_url=f"/jobs/{job_id}/stream",
    )


@app.get("/jobs/{job_id}")
async def status(job_id: str) -> dict:
    state = await app.state.redis.hgetall(JOB_PREFIX + job_id)
    if not state:
        raise HTTPException(404, "unknown job")
    return {k: json.loads(v) for k, v in state.items()}


# ---------------------------------------------------------------------------
# WebSocket — stream progress + tokens from the worker.
# The worker publishes to channel:tokens:<job_id>; this endpoint forwards.
# ---------------------------------------------------------------------------
@app.websocket("/jobs/{job_id}/stream")
async def stream(ws: WebSocket, job_id: str) -> None:
    await ws.accept()
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe(CHANNEL_PREFIX + job_id)
    try:
        # Send current job snapshot once.
        snap = await status(job_id)  # may raise 404 — let it
        await ws.send_json({"event": "snapshot", "data": snap})
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                await ws.send_text(msg["data"])
            await asyncio.sleep(0)
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.unsubscribe(CHANNEL_PREFIX + job_id)
        await pubsub.close()
