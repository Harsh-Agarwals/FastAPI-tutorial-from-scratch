# Notes — Chapter 02

## ASGI in one paragraph

FastAPI sits on top of **Starlette**, which sits on top of the **ASGI**
spec. ASGI is "WSGI but async": uvicorn (the server) hands FastAPI an
`(scope, receive, send)` triple. Everything else — routing, deps,
Pydantic — is built on top.

## What `Request.state` is for

A scratch namespace per request. Common uses:

- `request.state.request_id` (we did this)
- `request.state.user` (set by an auth middleware)
- `request.state.db` (a per-request DB session — though Depends is cleaner)

## Performance considerations

- Each middleware adds a few microseconds. Five is fine, fifty is silly.
- Middleware that does IO (e.g., looking up a user in Redis) is
  **on every request** — cache aggressively.
- For very hot paths, prefer dependencies (chapter 4) over middleware:
  they only run on the routes that declare them.

## Debugging

When something behaves unexpectedly, ask:

1. Did the request even reach the handler? (Add a log at the top.)
2. Which middleware mutated the response?
3. Are there *multiple* uvicorn workers? Logs interleave across them.
