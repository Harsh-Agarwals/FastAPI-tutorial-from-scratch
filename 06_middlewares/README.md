# 06 — Middlewares

Middleware is the place for **cross-cutting concerns**: logging, CORS,
compression, security headers, request limits, tracing. The pattern is
always the same:

```python
class MyMW(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # do stuff before
        response = await call_next(request)
        # do stuff after
        return response
```

## Run

```bash
uvicorn 06_middlewares.app:app --reload --port 8000

# See compression + logging
curl -s -H 'Accept-Encoding: gzip' http://localhost:8000/big -o /dev/null -w '%{size_download} bytes\n'
curl -s -H 'Accept-Encoding: identity' http://localhost:8000/big -o /dev/null -w '%{size_download} bytes\n'

# Body too large (413)
dd if=/dev/zero bs=1024 count=2048 2>/dev/null | curl -i -X POST --data-binary @- http://localhost:8000/echo

# Inspect security headers
curl -i http://localhost:8000/ | head
```

## What each middleware buys you

| Middleware              | Concern                                | Watch out for                                  |
|-------------------------|----------------------------------------|------------------------------------------------|
| `CORSMiddleware`        | Browser cross-origin permission        | `allow_origins=["*"]` + `allow_credentials=True` is invalid |
| `GZipMiddleware`        | Smaller responses on the wire          | CPU cost on tiny payloads — set `minimum_size` |
| `AccessLogMiddleware`   | Per-request log + timing               | Don't log full bodies (PII, size)              |
| `SecurityHeadersMW`     | Defaults that browsers respect         | Tune CSP; HSTS only over HTTPS                 |
| `BodySizeLimitMW`       | Early reject of huge uploads (DoS)     | Use `Content-Length`; streams need extra work  |

## Ordering rules

`add_middleware(X)` puts X **on top**, so it sees the request *first*
and the response *last*. Add inner-most first:

```python
app.add_middleware(BodySizeLimitMW)   # innermost
app.add_middleware(SecurityHeadersMW)
app.add_middleware(AccessLogMW)       # outermost — sees everything
```

A common mistake: putting CORS *inside* an auth middleware. Browsers
need CORS headers on preflight responses **before** auth runs, so CORS
must be **outermost** for those requests.

## Exercises

1. Build a `RequestIDMiddleware` that reads `X-Request-ID` from the
   client (if present) and falls back to a UUID. Push it into
   `request.state.request_id` and the response.
2. Add a `MaintenanceMiddleware` that returns 503 globally when the
   env var `MAINTENANCE=1` is set.
3. Make `BodySizeLimitMW` truly streaming-safe: wrap `request.receive`
   to count bytes and abort early.
