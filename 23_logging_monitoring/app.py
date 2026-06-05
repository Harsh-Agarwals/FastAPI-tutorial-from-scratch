"""
Chapter 23 — Logging & Monitoring.

We:
- configure structured (JSON) logging with structlog
- attach a request id to every log inside a request
- expose /metrics with counters and histograms (no Prometheus dep needed)
- show a basic /healthz and /readyz pair

Run:
    uvicorn 23_logging_monitoring.app:app --reload --port 8000
"""
from __future__ import annotations

import contextvars
import logging
import os
import time
import uuid
from collections import defaultdict

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

# --- Configure structlog -----------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# A context-var so every log inside a single request carries request_id.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def _inject_request_id(_, __, event_dict):
    event_dict["request_id"] = request_id_var.get()
    return event_dict


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_request_id,
        structlog.processors.JSONRenderer(),  # one JSON line per log
    ],
    wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, LOG_LEVEL)),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger()


# --- Tiny in-memory metrics (no Prometheus dependency) ----------------------
class Metrics:
    def __init__(self) -> None:
        self.counters: dict[tuple[str, frozenset], int] = defaultdict(int)
        self.hist_ms: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, **labels) -> None:
        self.counters[(name, frozenset(labels.items()))] += 1

    def observe(self, name: str, value_ms: float) -> None:
        self.hist_ms[name].append(value_ms)

    def render(self) -> str:
        lines: list[str] = []
        for (name, lbls), val in self.counters.items():
            l = ",".join(f'{k}="{v}"' for k, v in sorted(lbls))
            suffix = f"{{{l}}}" if l else ""
            lines.append(f"{name}{suffix} {val}")
        for name, values in self.hist_ms.items():
            if not values:
                continue
            lines.append(f"{name}_count {len(values)}")
            lines.append(f"{name}_sum {sum(values):.3f}")
            for q in (0.5, 0.9, 0.99):
                idx = max(0, int(q * len(values)) - 1)
                lines.append(f"{name}{{quantile=\"{q}\"}} {sorted(values)[idx]:.3f}")
        return "\n".join(lines) + "\n"


metrics = Metrics()


# --- Logging + metrics middleware --------------------------------------------
class LoggingMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_crashed", path=request.url.path)
            metrics.inc("http_errors_total", path=request.url.path)
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=round(elapsed_ms, 2),
            )
            metrics.inc(
                "http_requests_total",
                method=request.method,
                path=request.url.path,
                status=str(response.status_code),
            )
            metrics.observe("http_request_duration_ms", elapsed_ms)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


app = FastAPI(title="Chapter 23 — Logging & Monitoring")
app.add_middleware(LoggingMetricsMiddleware)


# --- Health / readiness ------------------------------------------------------
@app.get("/healthz")
def healthz() -> dict:
    """Liveness: is this process alive?  Never depends on external systems."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict:
    """Readiness: can this process accept traffic? Check deps here."""
    # Toy check; real ones touch DB / Redis with short timeouts.
    return {"status": "ready"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics_route() -> str:
    return metrics.render()


# --- Some demo routes that emit interesting logs / metrics ------------------
@app.get("/work")
async def work(slow_ms: int = 0) -> dict:
    log.info("doing_work", slow_ms=slow_ms)
    if slow_ms:
        import asyncio
        await asyncio.sleep(slow_ms / 1000)
    return {"ok": True}


@app.get("/boom")
def boom() -> dict:
    log.warning("about_to_crash")
    raise RuntimeError("on purpose")
