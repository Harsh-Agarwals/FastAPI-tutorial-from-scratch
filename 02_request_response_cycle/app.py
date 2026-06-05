"""
Chapter 02 — The Request / Response Cycle

We make the lifecycle *visible*. Hit any endpoint and you will see, in
the response headers and logs, every stage a request travels through.

Stages (in order):
    Client
      │
      ▼
    ASGI server (uvicorn)
      │
      ▼
    Middleware A   (outer)
      │
      ▼
    Middleware B   (inner)
      │
      ▼
    Dependency resolution
      │
      ▼
    Route handler          <-- your code
      │
      ▼
    Pydantic response serialization
      │
      ▼
    Middleware B (outgoing)
      │
      ▼
    Middleware A (outgoing)
      │
      ▼
    Client

Run:
    uvicorn 02_request_response_cycle.app:app --reload --port 8000
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Annotated

from fastapi import FastAPI, Header, Request
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ch02")

app = FastAPI(title="Chapter 02 — Request/Response Cycle")


# --------------------------------------------------------------------------
# Middleware A: assigns a request id + measures total time.
# Middleware runs in an "onion" pattern. The first one added is the outermost
# (last to see the response). Order matters.
# --------------------------------------------------------------------------
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        log.info("[A in ] %s %s id=%s", request.method, request.url.path, req_id)

        # Stash the id on the request state — handlers can read it.
        request.state.request_id = req_id
        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.2f}"
        log.info("[A out] %s %s id=%s took=%.2fms", request.method, request.url.path, req_id, elapsed_ms)
        return response


# --------------------------------------------------------------------------
# Middleware B: shows we run *inside* of A.
# --------------------------------------------------------------------------
class TraceStageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        log.info("  [B in ] before handler")
        response = await call_next(request)
        log.info("  [B out] after handler")
        response.headers["X-Stage"] = "middleware-B-visited"
        return response


# Add them in reverse-application order: B is added first => B is inner.
app.add_middleware(TraceStageMiddleware)
app.add_middleware(RequestIDMiddleware)


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
@app.get("/")
async def echo(
    request: Request,
    user_agent: Annotated[str | None, Header()] = None,
):
    """Returns a summary of the inbound request — proof of what FastAPI saw."""
    log.info("    [handler] running")
    return {
        "request_id": request.state.request_id,
        "method": request.method,
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client": request.client.host if request.client else None,
        "user_agent": user_agent,
        # Don't dump *all* headers in real code — they may contain secrets.
        "headers_seen": list(request.headers.keys()),
    }


@app.get("/slow")
async def slow():
    """Sleep to make `X-Process-Time-ms` obviously larger."""
    import asyncio

    await asyncio.sleep(0.3)
    return {"status": "done"}
