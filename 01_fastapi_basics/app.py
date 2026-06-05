"""
Chapter 01 — FastAPI Basics

Goal: feel the shape of a FastAPI app in ~80 lines.

You will see:
- routes (GET / POST)
- path params, query params
- a request body validated by Pydantic
- response models (what goes OUT is also typed)
- explicit status codes
- a tiny in-memory "DB" so the example feels real

Run:
    uvicorn 01_fastapi_basics.app:app --reload --port 8000

Then open:
    http://localhost:8000/docs   (Swagger UI — auto-generated)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="Chapter 01 — FastAPI Basics",
    version="0.1.0",
    description="The smallest FastAPI app that still demonstrates the essentials.",
)


# --------------------------------------------------------------------------
# Pydantic models — the contract between the API and the outside world.
# Why use them?
#   - Automatic validation (rejects bad data with a 422 before your code runs)
#   - Automatic OpenAPI / Swagger docs
#   - Free serialization (dict -> JSON, JSON -> typed Python objects)
# --------------------------------------------------------------------------
class BookIn(BaseModel):
    """What clients send when CREATING a book."""

    title: str = Field(min_length=1, max_length=120)
    author: str = Field(min_length=1, max_length=80)
    year: int = Field(ge=1450, le=2100)  # Gutenberg-ish lower bound


class BookOut(BookIn):
    """What we send BACK to clients. Includes the server-assigned id."""

    id: int


# Pretend database. In real life this would be Postgres + a repository layer.
_BOOKS: dict[int, BookOut] = {}
_NEXT_ID = 3

_BOOKS[1] = BookOut(
    id=1,
    title="The Hobbit",
    author="J.R.R. Tolkien",
    year=1937
)

_BOOKS[2] = BookOut(
    id=2,
    title="1984",
    author="George Orwell",
    year=1949
)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """Health-check style root. Visit `/docs` to see the interactive UI."""
    return {"status": "ok", "chapter": "01_fastapi_basics"}


@app.get("/books", response_model=list[BookOut], tags=["books"])
def list_books(
    # Query params: `?author=...&limit=10` — typed, validated, documented.
    author: Annotated[str | None, Query(description="Filter by author (exact)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[BookOut]:
    items = list(_BOOKS.values())
    if author:
        items = [b for b in items if b.author == author]
    return items[:limit]


@app.get("/books/{book_id}", response_model=BookOut, tags=["books"])
def get_book(
    # Path params live in the URL itself. `Path(...)` lets us add validation.
    book_id: Annotated[int, Path(ge=1, description="Server-assigned book id")],
) -> BookOut:
    if book_id not in _BOOKS:
        # Always raise HTTPException for client-facing errors.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return _BOOKS[book_id]


@app.post(
    "/books",
    response_model=BookOut,
    status_code=status.HTTP_201_CREATED,  # 201 = "Created" is the *correct* status for POST.
    tags=["books"],
)
def create_book(payload: BookIn) -> BookOut:
    """`payload: BookIn` tells FastAPI to read JSON, validate, and inject it."""
    global _NEXT_ID
    book = BookOut(id=_NEXT_ID, **payload.model_dump())
    _BOOKS[_NEXT_ID] = book
    _NEXT_ID += 1
    return book


@app.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["books"])
def delete_book(book_id: int) -> None:
    """204 means: success, and there is no body. Don't return anything."""
    if _BOOKS.pop(book_id, None) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    return None
