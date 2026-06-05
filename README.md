# FastAPI + AI Engineering Lab

A chapter-by-chapter, hands-on learning repository that takes you from
FastAPI fundamentals to a production-grade AI PDF Summarizer.

This is **not** a single monolithic project. It is an **engineering
playground** — each folder is an independently runnable mini-project
that isolates **one concept** so you can build real intuition.

---

## Learning philosophy

We do not want to "ship features". We want to deeply understand:

- backend engineering fundamentals
- the FastAPI request/response model
- the async event loop
- threads vs processes vs coroutines
- CPU-bound vs IO-bound workloads
- caching, queues, rate limiting, streaming
- AI integration patterns (LLMs, embeddings, vector search)
- scalable production architecture

The final chapter (`29_ai_pdf_summarizer`) combines every prior concept
into a real-world AI service.

---

## Repository map

| #  | Folder                          | What you learn                                            |
|----|---------------------------------|-----------------------------------------------------------|
| 01 | `01_fastapi_basics`             | Routes, params, request body, response models             |
| 02 | `02_request_response_cycle`     | How FastAPI handles a request end-to-end                  |
| 03 | `03_pydantic_models`            | Validation, serialization, custom validators              |
| 04 | `04_dependency_injection`       | `Depends`, scopes, testing seams                          |
| 05 | `05_authentication`             | API keys, OAuth2 + JWT, password hashing                  |
| 06 | `06_middlewares`                | Request lifecycle hooks, custom middleware                |
| 07 | `07_error_handling`             | Exception handlers, problem-details, RFC 7807             |
| 08 | `08_file_uploads`               | Async file uploads, streaming, validation, security       |
| 09 | `09_background_tasks`           | `BackgroundTasks`, job IDs, polling                       |
| 10 | `10_async_programming`          | `async`/`await`, event loop, blocking pitfalls            |
| 11 | `11_asyncio_experiments`        | `gather`, semaphores, cancellation, timeouts              |
| 12 | `12_threading`                  | `ThreadPoolExecutor`, GIL, thread safety                  |
| 13 | `13_multiprocessing`            | `ProcessPoolExecutor`, CPU-heavy work                     |
| 14 | `14_cpu_vs_io_bound`            | Benchmarks across sync / async / threads / processes      |
| 15 | `15_concurrency_patterns`       | Fan-out/fan-in, pipelines, backpressure                   |
| 16 | `16_websockets`                 | Real-time, streaming tokens, disconnect handling          |
| 17 | `17_streaming_responses`        | `StreamingResponse`, SSE, generator-based responses       |
| 18 | `18_rate_limiting`              | Token bucket, sliding window, Redis-based limits          |
| 19 | `19_caching`                    | In-memory, Redis, TTL, invalidation, AI response cache    |
| 20 | `20_redis_intro`                | Strings, hashes, lists, pub/sub, patterns                 |
| 21 | `21_task_queues`                | Producer/consumer, Celery concepts, retries               |
| 22 | `22_database_async`             | `asyncpg`, SQLAlchemy 2.x async, transactions             |
| 23 | `23_logging_monitoring`         | Structured logging, request IDs, metrics                  |
| 24 | `24_ai_integration`             | LLM calls, retries, batching, timeouts (mockable)         |
| 25 | `25_embeddings_intro`           | What embeddings are, distances, building intuition        |
| 26 | `26_vector_search`              | In-memory vector index, cosine similarity, FAISS notes    |
| 27 | `27_pdf_processing`             | PDF parsing, chunking, preprocessing                      |
| 28 | `28_parallel_pdf_processing`    | Concurrent chunk summarization, semaphores                |
| 29 | `29_ai_pdf_summarizer`          | Capstone: upload → queue → summarize → stream → cache     |
| 30 | `30_scalability_concepts`       | Horizontal scaling, statelessness, load balancing         |
| 31 | `31_system_design_notes`        | Architecture diagrams and design notes                    |
|    | `notebooks/`                    | Cross-cutting Jupyter experiments                         |

---

## Setup (one-time)

```bash
# 1. Python 3.11+ recommended
python --version

# 2. Create a virtualenv at the repo root
python -m venv .venv
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\activate            # Windows

# 3. Install all dependencies for every chapter
pip install -r requirements.txt

# 4. Copy environment variables
cp .env.example .env
```

Some chapters need Redis. The easiest way:

```bash
docker run -d --name redis -p 6379:6379 redis:7
```

---

## How to run any chapter

Every chapter is independently runnable. **From the repo root**:

```bash
uvicorn 01_fastapi_basics.app:app --reload --port 8000
```

> **Why "from the repo root"?** Folder names like `01_fastapi_basics`
> start with a digit, so Python's `import` keyword cannot reference
> them — but `importlib` (which uvicorn and the later chapters use)
> can. Running from the repo root keeps every chapter on `sys.path`.

You can also `cd` into a chapter and run `uvicorn app:app --reload`
for a simpler local invocation. Each chapter
contains:

- `app.py` or `main.py` — the FastAPI service
- `README.md` — concept explanation, why/how, edge cases
- `notes.md` — scratch notes, gotchas, debugging tips
- `experiments/*.ipynb` — Jupyter notebooks for hands-on exploration
- `requests.http` — sample requests (works in VS Code REST Client / Postman)

---

## Suggested learning order

1. Read the chapter's `README.md` first (intuition).
2. Read `app.py` line by line. Most files are kept short on purpose.
3. Start the server and hit endpoints with `requests.http` or `curl`.
4. Open the notebook in `experiments/` and run cells.
5. Read `notes.md` for the deeper "why" + scalability discussion.
6. Try the **Exercises** at the bottom of each README.

Move forward only when intuition feels solid. Re-running notebooks
on different machines (laptop vs server) gives different timings —
that itself is a great lesson in concurrency.

---

## House style

- Async-first where it matters.
- Type hints everywhere.
- Pydantic models for all request/response bodies.
- Small, focused files. Production patterns, not toy code.
- Comments explain **why**, not what.

---

## Capstone preview — Chapter 29

The AI PDF Summarizer demonstrates:

- `POST /upload` — async, validated PDF upload
- background queue dispatches chunked summarization
- `GET /jobs/{id}` — polling
- `WS /jobs/{id}/stream` — live token streaming
- Redis-based cache for repeat summaries
- structured logs, rate limiting, graceful errors

It is the same pattern used by real production AI services.

Happy hacking. The point is the journey, not the destination.
