# 31 — System Design Notes

Reference diagrams and reasoning you can reuse for your own AI services.

## 1. The "AI Service" reference architecture

```
                                ┌──────────────────────┐
        ┌─────────┐              │   Identity / Auth     │
        │ Clients │ ───────────▶ │   (OAuth, JWT, KMS)   │
        └─────────┘              └──────────┬────────────┘
                                            │
                ┌───────────────────────────▼──────────────────────┐
                │                     API Gateway                   │
                │  CORS · rate-limit · WAF · request-id · tracing   │
                └───────────────────────────┬──────────────────────┘
                                            │
              ┌───────────────┬─────────────┴───────────────┬──────────────────┐
              ▼               ▼                             ▼                  ▼
   ┌──────────────────┐ ┌──────────────────┐  ┌──────────────────────┐  ┌─────────────────┐
   │  HTTP API (Stateless)│ │  WebSocket Gateway  │  │  Background Workers   │  │  Schedulers      │
   │  FastAPI / uvicorn   │ │  (token streaming)  │  │  (PDF parse / summary)│  │  (cron / Celery) │
   └─────────┬────────────┘ └──────────┬───────────┘  └──────────┬───────────┘  └─────────────────┘
             │                         │                         │
   ┌─────────▼───────────┐    ┌────────▼─────────┐    ┌──────────▼──────────┐
   │  Postgres (data)    │    │  Redis (pubsub,  │    │  Object Store (S3)  │
   │  pgvector (RAG)     │    │  cache, queues)  │    │  (PDFs, artifacts)  │
   └─────────────────────┘    └──────────────────┘    └─────────────────────┘
                                            │
                                            ▼
                                  ┌───────────────────┐
                                  │  External LLM API  │  ← retries, semaphore, fallback
                                  │  (OpenAI/Anthropic)│
                                  └───────────────────┘
```

## 2. Request → Response (chapter 29 anchor)

```
POST /upload      ──▶  validate ─▶ stream to S3 ─▶ row in DB ─▶ 201 + file_id
POST /summarize/X ──▶  enqueue job in Redis ─▶ 202 + job_id, urls
GET  /jobs/X      ──▶  read hash from Redis ─▶ JSON
WS   /jobs/X/strm ──▶  subscribe to pubsub:tokens:X ─▶ forward
```

## 3. Data flow for AI summarisation

```
PDF (S3) ─▶ parse (process pool) ─▶ chunks ─┐
                                              ▼
                              embed batch ─▶ vector store
                                              │
                            user prompt ─▶ retrieve top-k ─▶ build prompt
                                              ▼
                                          LLM call(s)
                                              ▼
                                         streamed answer
```

## 4. Failure modes & responses (cheat sheet)

| Failure                          | Detect                     | Mitigate                                        |
|----------------------------------|----------------------------|-------------------------------------------------|
| LLM 429                          | response code              | semaphore, jittered backoff, second key         |
| LLM timeout                      | `asyncio.TimeoutError`     | retry once, then partial answer                 |
| Worker crash                     | missed heartbeat           | Redis Streams + consumer-group `XAUTOCLAIM`     |
| Redis unavailable                | startup ping fails         | API responds 503; alarm; queue paused           |
| Postgres saturated               | latency spike              | pgbouncer; smaller pool per worker              |
| Huge upload                      | Content-Length / streaming | reject at edge, cap in app, S3 multipart        |
| Bad PDF                          | parse exception            | 422 with clear error; do not crash worker       |

## 5. Capacity worksheet

A handy back-of-envelope to sanity-check a design.

```
Target: 100 PDF summaries / minute (peak)

Assumptions
  - Avg PDF: 20 pages, 12 chunks
  - Per chunk: 0.7s LLM latency, ~2k tokens
  - 12 chunks * 0.7s / (5 concurrent)  ≈  1.7s wall-clock per doc
  - Reduce call: 0.5s

Wall-clock per doc:   ~2.5 s
LLM RPS budget needed: 100 / 60 * (12 + 1) ≈ 22 LLM RPS sustained

Workers needed (per box): 1 doc at a time → 100 / 60 / (1/2.5) ≈ 4-6
Add 2x safety:                                       8-12 worker procs

Tokens / day:        100 * 60 * 24 * 13 chunks * 2k tokens ≈ 3.7 B
Token budget per doc: ~26k tokens
Cost / month at $X / 1k tokens: do the math, alarm at 80%
```

## 6. Diagrams to draw before coding

For every new service, sketch:

1. **Boxes and arrows** — who talks to whom.
2. **Sequence diagram** of the happy path.
3. **Failure tree** — what happens if each box dies.
4. **Capacity worksheet** like above.

15 minutes of drawing saves weeks of refactoring.

## 7. Final advice

- **Make boring decisions** for everything outside your core value.
- **Cache, retry, time-out** are the holy trinity of robust services.
- **Logs > metrics > traces** for debugging *right now*.
- **Optimise tail latency**, not average. P99 is the user experience.
- **Idempotency tokens are free joy** — design them in from day one.

Now go build something real with this lab.
