# Notes — Chapter 01

## Why FastAPI over Flask?

- Async-first. Async is a first-class citizen, not a bolt-on.
- Pydantic v2 is *fast* (Rust core) and gives free validation + docs.
- Type hints stop being decorative; they become the API contract.
- Swagger UI / ReDoc are auto-generated, always in sync.

## Sync vs async handlers

In this chapter every handler is sync. That is fine because the
handlers do **zero IO**. The moment you talk to a DB / network / disk,
prefer `async def` so you do not block the event loop.

A blocking handler in an async server is a classic production outage —
we will demonstrate this in chapter 10.

## Debugging tips

- `--reload` watches files; great in dev, never use in prod.
- If `/docs` looks empty, check that `@app.get(...)` decorators are on
  module-level functions, not inside `if __name__ == "__main__"`.
- 422 errors include a JSON `detail` array pointing at the exact field
  that failed validation. Read it carefully before "fixing" code.

## Scalability discussion (preview)

Even this toy app would scale horizontally as long as:

1. State is not in memory (our `_BOOKS` dict breaks this — fix in ch 22).
2. Each request is short and non-blocking.
3. We deploy multiple uvicorn workers behind a load balancer.

We will revisit this in chapter 30.
