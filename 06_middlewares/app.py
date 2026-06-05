"""
Chapter 06 — Middlewares

Building blocks for cross-cutting concerns. We implement four real,
production-shaped middlewares:

1. CORS (built-in)
2. GZip compression (built-in)
3. Custom: structured request logger with timing
4. Custom: simple security headers
5. Custom: body size guard (early reject of huge payloads)

Run:
    uvicorn 06_middlewares.app:app --reload --port 8000
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("ch06")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Chapter 06 — Middlewares")


# --- (1) CORS — let browsers from listed origins call our API ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- (2) GZip — compress big JSON responses automatically -------------------
app.add_middleware(GZipMiddleware, minimum_size=500)


# --- (3) Structured request logger ------------------------------------------
class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Make sure failures still get logged with timing.
            log.exception("request crashed id=%s", req_id)
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info(
                "access path=%s method=%s status=%d ms=%.2f id=%s ip=%s",
                request.url.path,
                request.method,
                status_code,
                elapsed_ms,
                req_id,
                request.client.host if request.client else "-",
            )
            response.headers["X-Request-ID"] = req_id
            return response


# --- (4) Security headers ----------------------------------------------------
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=()",
    # In production add: "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload"
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response


# --- (5) Body-size guard — reject before reading the whole body --------------
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_bytes: int = 1 * 1024 * 1024):  # 1 MiB
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        # 1) Trust Content-Length if present — fast path.
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > self.max_bytes:
            return JSONResponse(
                {"detail": f"Body too large; limit is {self.max_bytes} bytes"},
                status_code=413,
            )
        # 2) Streaming clients may not set Content-Length. For real
        #    safety, peek at the stream — out of scope for the demo.
        return await call_next(request)


# Order matters: add inner-most first.
app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024 * 1024)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AccessLogMiddleware)


@app.get("/")
def root() -> dict[str, str]:
    return {"msg": "hello"}


@app.get("/big")
def big_payload() -> dict:
    # Big enough to trigger GZip
    return {"items": [{"i": i, "name": f"item-{i}" * 4} for i in range(2000)]}


@app.post("/echo")
async def echo(request: Request) -> Response:
    body = await request.body()
    return JSONResponse({"received_bytes": len(body)})
