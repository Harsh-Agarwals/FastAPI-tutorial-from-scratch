"""
Chapter 07 — Error handling

Good error responses are part of your API contract. Bad ones leak
stack traces, confuse clients, and hide bugs.

We implement a small **Problem Details for HTTP APIs** (RFC 7807)
response shape and wire it to:
- domain exceptions (your own)
- FastAPI's validation errors (`RequestValidationError`)
- unexpected exceptions (the catch-all)

Run:
    uvicorn 07_error_handling.app:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

log = logging.getLogger("ch07")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Chapter 07 — Error Handling")


# --------------------------------------------------------------------------
# Domain errors — model real business failures, not just HTTP codes.
# --------------------------------------------------------------------------
class DomainError(Exception):
    """Base class for any 'business' error we know how to render."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class InsufficientBalance(DomainError):
    status_code = 422
    code = "insufficient_balance"


# --------------------------------------------------------------------------
# RFC 7807 envelope. Stable shape across all errors.
# --------------------------------------------------------------------------
class Problem(BaseModel):
    type: str = Field(default="about:blank", description="URI identifier for the error class")
    title: str
    status: int
    code: str
    detail: str | None = None
    instance: str | None = None       # the path that produced the error
    errors: list[dict] | None = None  # validation errors live here


def _problem_response(req: Request, *, status_code: int, code: str, title: str, detail: str | None = None, errors=None) -> JSONResponse:
    body = Problem(
        title=title,
        status=status_code,
        code=code,
        detail=detail,
        instance=str(req.url),
        errors=errors,
    ).model_dump(exclude_none=True)
    return JSONResponse(body, status_code=status_code, media_type="application/problem+json")


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------
@app.exception_handler(DomainError)
async def handle_domain(req: Request, exc: DomainError) -> JSONResponse:
    return _problem_response(req, status_code=exc.status_code, code=exc.code, title=exc.__class__.__name__, detail=exc.detail)


@app.exception_handler(HTTPException)
async def handle_http(req: Request, exc: HTTPException) -> JSONResponse:
    return _problem_response(req, status_code=exc.status_code, code="http_error", title=exc.__class__.__name__, detail=str(exc.detail))


@app.exception_handler(RequestValidationError)
async def handle_validation(req: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem_response(
        req,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        title="Validation failed",
        detail="One or more fields are invalid.",
        errors=exc.errors(),
    )


@app.exception_handler(Exception)
async def handle_unexpected(req: Request, exc: Exception) -> JSONResponse:
    # Log full traceback server-side; never leak it to the client.
    log.exception("unhandled exception path=%s", req.url.path)
    return _problem_response(
        req,
        status_code=500,
        code="internal_error",
        title="Internal Server Error",
        detail="Something went wrong. Please try again later.",
    )


# --------------------------------------------------------------------------
# Demo endpoints — each triggers a different category.
# --------------------------------------------------------------------------
class TransferIn(BaseModel):
    from_account: str = Field(min_length=1)
    to_account: str = Field(min_length=1)
    amount: float = Field(gt=0)


_BALANCES = {"acc-1": 100.0, "acc-2": 50.0}


@app.post("/transfer")
def transfer(t: TransferIn) -> dict:
    if t.from_account not in _BALANCES:
        raise NotFound(f"Account {t.from_account} not found")
    if t.to_account not in _BALANCES:
        raise NotFound(f"Account {t.to_account} not found")
    if _BALANCES[t.from_account] < t.amount:
        raise InsufficientBalance(f"Need {t.amount}, have {_BALANCES[t.from_account]}")
    _BALANCES[t.from_account] -= t.amount
    _BALANCES[t.to_account] += t.amount
    return {"ok": True, "balances": _BALANCES}


@app.get("/boom")
def boom() -> dict:
    # Unexpected error path — exercises the catch-all handler.
    return {"x": 1 / 0}


@app.get("/teapot")
def teapot() -> dict:
    # HTTPException-driven path.
    raise HTTPException(status_code=418, detail="I'm a teapot")
