# 23 — Logging & Monitoring

If you cannot observe it, you cannot operate it.

## Three pillars (the textbook list)

| Pillar  | What it answers                  | Tools                       |
|---------|----------------------------------|-----------------------------|
| Logs    | "What happened?"                 | structlog, Loki, CloudWatch |
| Metrics | "How often / how fast?"          | Prometheus, Datadog         |
| Traces  | "What was the request path?"     | OpenTelemetry, Tempo, Honeycomb |

This chapter wires the first two. Tracing is one library swap away.

## Run

```bash
uvicorn 23_logging_monitoring.app:app --reload --port 8000

curl http://localhost:8000/work?slow_ms=100
curl http://localhost:8000/work?slow_ms=300
curl http://localhost:8000/boom -i
curl http://localhost:8000/metrics
```

You should see JSON logs in the terminal:
```json
{"event":"request","level":"info","timestamp":"...","request_id":"abcd","method":"GET","path":"/work","status":200,"ms":102.4}
```

And metrics like:
```
http_requests_total{method="GET",path="/work",status="200"} 2
http_request_duration_ms_count 2
http_request_duration_ms_sum 401.2
http_request_duration_ms{quantile="0.99"} 312.4
```

## The "request id" trick

A `contextvars.ContextVar` lets every log inside a request automatically
carry the same id without you passing it around. Combined with the
`X-Request-ID` response header, you can paste an id from a user bug
report and find every log line involved. Magic.

## Logs: do / don't

DO:
- log JSON
- include request id, user id (hashed), and key business fields
- log durations as numbers, not formatted strings
- log warnings on retries, errors on failures, info on success

DON'T:
- log request/response bodies — they may contain secrets / PII
- log on every tight-loop iteration — burns disk
- log a stack trace at INFO — reserve `exception()` for unhandled errors

## Metrics: what to record

- `http_requests_total{method,path,status}` (counter)
- `http_request_duration_ms` (histogram) — for p50/p90/p99
- `ai_tokens_total{model}` (counter) — cost insight
- `job_queue_depth` (gauge)
- `cache_hits_total`, `cache_misses_total`

## Health vs readiness

| Endpoint  | Purpose                              | Should depend on Redis/DB? |
|-----------|--------------------------------------|----------------------------|
| `/healthz`| "process is alive"                   | **No** (else flaky restarts) |
| `/readyz` | "ready to receive traffic"           | Yes (briefly, with timeouts) |

Kubernetes uses `liveness` (kill if not ok) vs `readiness` (don't send
traffic if not ok). Get the mapping right or your app gets killed
during normal DB blips.

## Exercises

1. Add a `path_template` to metrics labels (`/jobs/{id}` not `/jobs/abc`)
   to avoid cardinality explosion. Hint: `request.scope["route"].path`.
2. Add OpenTelemetry tracing — `opentelemetry-instrumentation-fastapi`
   gives you spans for free.
3. Track AI token usage per endpoint (you'll need this in chapter 24).
