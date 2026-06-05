# 01 — FastAPI Basics

> The smallest FastAPI app that still teaches the **right** habits.

## What you will learn

- How a route is defined (`@app.get`, `@app.post`, ...)
- Path params vs query params vs request body
- Why we use Pydantic `BaseModel` for input and output
- HTTP status codes done correctly (`201`, `204`, `404`)
- Swagger UI for free at `/docs`

## Run it

```bash
# From the repo root
uvicorn 01_fastapi_basics.app:app --reload --port 8000
```

Then open:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Try it (curl)

```bash
# Create a book (POST + JSON body)
curl -X POST http://localhost:8000/books \
  -H 'Content-Type: application/json' \
  -d '{"title":"The Pragmatic Programmer","author":"Hunt","year":1999}'

# List books, filter by author
curl 'http://localhost:8000/books?author=Hunt&limit=5'

# Get one
curl http://localhost:8000/books/1

# Delete it (no body in 204)
curl -X DELETE http://localhost:8000/books/1 -v
```

## Mental model

A FastAPI handler is a **typed function**. FastAPI inspects the
function signature and turns it into:

| Annotation                  | Where it comes from         |
|-----------------------------|-----------------------------|
| `book_id: int`              | Path (`/books/{book_id}`)   |
| `author: str \| None = None`| Query string (`?author=`)   |
| `payload: BookIn`           | JSON request body           |
| `Header(...)`, `Cookie(...)`| Headers / cookies (later)   |
| `Depends(...)`              | Dependency injection (ch 4) |

The same signature gives you:

1. **Runtime validation** (returns `422 Unprocessable Entity` on bad input)
2. **OpenAPI schema** (Swagger / ReDoc)
3. **Editor autocompletion**
4. **`response_model=` lets you control what leaks back out**

That last point matters in production: never return your DB model
directly. Return a `*Out` model — it strips internal fields like
`password_hash` automatically.

## Status code cheat sheet

| Code | When                                                              |
|------|-------------------------------------------------------------------|
| 200  | Default. GET worked, body returned.                               |
| 201  | Created. POST that created a new resource. **Set this explicitly.** |
| 204  | No content. DELETE / "fire & forget". Body MUST be empty.         |
| 400  | Client sent something semantically wrong.                         |
| 401  | Not authenticated.                                                |
| 403  | Authenticated, but not allowed.                                   |
| 404  | Not found.                                                        |
| 409  | Conflict (e.g., duplicate unique value).                          |
| 422  | Validation failed. **FastAPI returns this for you.**              |
| 500  | You crashed. Surfaced via exception handlers (ch 7).              |

## Edge cases to think about

- What if `book_id` is a string in the URL? → FastAPI rejects with 422.
- What if a field is missing? → 422 with a clear error pointing at the field.
- What if you return a `dict` instead of `BookOut`? → It still works, but you
  lose the response-side validation and the OpenAPI contract weakens.
- What happens to `_BOOKS` if the server restarts? → Wiped. State in memory
  is **per-process**. We will fix this with a real DB in chapter 22.

## Exercises

1. Add a `PUT /books/{book_id}` endpoint (full replace).
2. Add a `PATCH /books/{book_id}` endpoint (partial update — hint: use a
   second Pydantic model where every field is `Optional`).
3. Add a query param `sort: Literal["title","year"] = "year"` to `GET /books`.
4. Notice what happens if you forget `response_model=` on a route, then add
   a private field (e.g. `secret_note`) and watch it leak out.
