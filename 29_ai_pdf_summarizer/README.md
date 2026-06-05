# 29 — Capstone: AI PDF Summarizer

The final project. We combine **every prior chapter** into one
production-shaped service.

## Architecture

```
┌──────────┐    POST /upload                  ┌─────────────┐
│  Client  │ ─────────────────────────────▶   │  FastAPI    │
│          │ ◀─ 201 + file_id                │  app        │
│          │    POST /summarize/{file_id}     │             │
│          │ ◀─ 202 + job_id, urls            │             │
│          │    GET  /jobs/{job_id}    ───▶   │             │
│          │ ◀─ status JSON                   │             │
│          │    WS   /jobs/{job_id}/stream    │             │
└──────────┘ ◀═══ live progress / tokens ═══  └──────┬──────┘
                                                     │ Redis: queue + state + pubsub
                                                     ▼
                                              ┌─────────────┐
                                              │   Worker    │
                                              │ ─ parse PDF │ (process pool)
                                              │ ─ summarise │ (asyncio + sem + cache)
                                              │ ─ reduce    │
                                              └─────────────┘
```

## How each chapter shows up

| Concept                          | Chapter | Where in code           |
|----------------------------------|:-------:|-------------------------|
| Pydantic models                  | 03      | `UploadOut`, `EnqueueOut`|
| Dependency injection (lifespan)  | 04      | `lifespan(app)`         |
| File uploads (streamed)          | 08      | `/upload`               |
| 202 + polling                    | 09      | `/summarize/{id}`       |
| Async / event loop               | 10      | every `async def`       |
| asyncio.gather / as_completed    | 11      | worker partial loop     |
| Process pool for CPU             | 13      | `ProcessPoolExecutor`   |
| Semaphore for LLM concurrency    | 11/15   | `MAX_CONCURRENT_LLM`    |
| WebSocket streaming              | 16      | `/jobs/{id}/stream`     |
| Caching (Redis)                  | 19      | `CACHE_PREFIX`          |
| Redis pub/sub                    | 20      | `_publish`              |
| Real task queue                  | 21      | `RPUSH` / `BLPOP`       |
| AI integration patterns          | 24      | `call_with_retry`       |
| PDF chunking                     | 27      | `_parse_chunks`         |
| Parallel summarisation           | 28      | worker `handle()`       |

## Run

```bash
docker run -d --name redis -p 6379:6379 redis:7

# Terminal 1
uvicorn 29_ai_pdf_summarizer.app:app --reload --port 8000

# Terminal 2
python -m 29_ai_pdf_summarizer.worker

# Terminal 3 — upload + enqueue
FID=$(curl -s -X POST -F "file=@./sample.pdf;type=application/pdf" \
  http://localhost:8000/upload | jq -r .file_id)

JOB=$(curl -s -X POST http://localhost:8000/summarize/$FID | jq -r .job_id)

# Poll status
curl -s http://localhost:8000/jobs/$JOB | jq

# Or stream
wscat -c ws://localhost:8000/jobs/$JOB/stream
```

## Why this design scales

- **Stateless API** — every uvicorn worker handles any request.
- **Durable jobs** — Redis queue survives restarts.
- **Horizontal workers** — start more `worker.py` processes for more
  throughput.
- **Backpressure** — queue depth limits, semaphore on LLM.
- **Cache** — repeated docs / chunks are free.
- **Observable** — status hash + pub/sub make progress visible.

## What this is NOT (yet)

For a real launch, add:

- **Auth** (chapter 5) — only allow the uploader to read their job.
- **Persistent storage** — put PDFs on S3 with pre-signed URLs.
- **DB** — store finished summaries in Postgres (chapter 22).
- **Rate limiting** (chapter 18) per-user, per-tenant.
- **Observability** (chapter 23) with Prometheus + traces.
- **Background retention** — delete files after N days.
- **A real LLM key** in `.env`. Right now it uses the mock.

## Exercises

1. Add auth: only the uploader can poll / stream their own jobs.
2. Add **idempotency** — `Idempotency-Key` header in `/upload` returns
   the same job id on retries within 24h.
3. Stream the *final reduce* token-by-token to the WebSocket using a
   provider that supports streaming completions.
4. Replace the in-memory pool with a separate worker service on a
   different host. The API does not need to change.
