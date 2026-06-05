"""
Chapter 04 — Dependency Injection (Depends)

`Depends(...)` is the most powerful primitive in FastAPI after the
router itself. Use it for:

- shared logic (pagination, current user, db session)
- resources with setup + teardown (yield-based deps)
- testability (swap implementations in tests)
- request-scoped caching (`use_cache=True` is the default)

Mental model: a dependency is just a function (or class) that returns
the value your handler needs. FastAPI calls it for you.

Run:
    uvicorn 04_dependency_injection.app:app --reload --port 8000
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

log = logging.getLogger("ch04")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Chapter 04 — Dependency Injection")


# --------------------------------------------------------------------------
# 1. Function dependency — shared pagination params.
# Use this everywhere you want "limit + offset" without copy-paste.
# --------------------------------------------------------------------------
def pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, int]:
    return {"limit": limit, "offset": offset}


PageParams = Annotated[dict[str, int], Depends(pagination)]


# --------------------------------------------------------------------------
# 2. Dependency that raises on failure (auth-ish).
# When a dep raises HTTPException, the handler never runs.
# --------------------------------------------------------------------------
def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> str:
    if x_api_key != "secret-key":  # in real code: compare against env / db
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


ApiKey = Annotated[str, Depends(require_api_key)]


# --------------------------------------------------------------------------
# 3. Yield-based dependency — setup + teardown (like a context manager).
# This is the pattern for DB sessions, network clients, file handles, etc.
# --------------------------------------------------------------------------
class FakeDB:
    """Stand-in for SQLAlchemy AsyncSession / asyncpg pool."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def query(self, sql: str) -> str:
        self.queries.append(sql)
        return f"result of: {sql}"


async def get_db() -> AsyncIterator[FakeDB]:
    db = FakeDB()
    log.info("db: opened")
    try:
        yield db
    finally:
        # Runs *after* the response is sent. Use it for cleanup.
        log.info("db: closed after %d queries", len(db.queries))


DB = Annotated[FakeDB, Depends(get_db)]


# --------------------------------------------------------------------------
# 4. Class dependency — when state / config is involved.
# --------------------------------------------------------------------------
class SearchFilter:
    """A class dep behaves like a function: `__call__` returns the value...
    ...except FastAPI just instantiates it from query params.
    """

    def __init__(
        self,
        q: str | None = None,
        tag: list[str] | None = Query(default=None),
    ) -> None:
        self.q = q
        self.tags = tag or []


SearchDep = Annotated[SearchFilter, Depends(SearchFilter)]


# --------------------------------------------------------------------------
# 5. Sub-dependencies + request-scoped caching.
# `pagination` runs once per request, even if used 3 times.
# --------------------------------------------------------------------------
def page_summary(p: PageParams) -> str:
    return f"limit={p['limit']} offset={p['offset']}"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/items")
async def list_items(page: PageParams, db: DB) -> dict:
    rows = await db.query(f"SELECT * FROM items LIMIT {page['limit']} OFFSET {page['offset']}")
    return {"page": page, "rows": rows}


@app.get("/secret")
async def secret(_: ApiKey) -> dict[str, str]:
    """Provide `X-API-Key: secret-key` or get a 401."""
    return {"message": "you are in"}


@app.get("/search")
async def search(filt: SearchDep, page: PageParams) -> dict:
    return {"q": filt.q, "tags": filt.tags, "page": page}


@app.get("/echo-page")
def echo_page(page: PageParams, summary: Annotated[str, Depends(page_summary)]) -> dict:
    # `pagination` is the parent of both deps; it runs only ONCE per request.
    return {"page": page, "summary": summary}


# --------------------------------------------------------------------------
# 6. Router-level / app-level dependencies.
# Apply auth to a whole group of routes without decorating each one.
# --------------------------------------------------------------------------
from fastapi import APIRouter

admin = APIRouter(prefix="/admin", dependencies=[Depends(require_api_key)])


@admin.get("/stats")
def admin_stats() -> dict:
    return {"users": 42, "items": 100}


app.include_router(admin)
