# 04 — Dependency Injection

`Depends(...)` is the single feature that scales FastAPI from "toy
script" to "well-organized service". Use it everywhere you would
otherwise copy-paste setup code into every handler.

## What is a dependency?

A callable (function, class, or generator) that FastAPI runs **before**
your handler and whose return value is passed in.

```python
def pagination(limit: int = 20, offset: int = 0) -> dict:
    return {"limit": limit, "offset": offset}

@app.get("/items")
def list_items(page: dict = Depends(pagination)): ...
```

## Five patterns you will use forever

1. **Shared query params** — pagination, filters, sorting.
2. **Auth** — a dep that raises 401/403 short-circuits the handler.
3. **Setup/teardown** — `async def get_db()` that `yield`s a session.
4. **Class deps** — when state or config is involved.
5. **Router-level deps** — apply a dep to every route in an APIRouter.

## Two superpowers

### Request-scoped cache (free)
The same dep called from multiple places in one request **runs once**.
That means our `pagination` only validates `limit` / `offset` once even
if 5 deps depend on it. Disable with `Depends(fn, use_cache=False)`.

### Override for tests
```python
app.dependency_overrides[get_db] = lambda: FakeDB()
```
This makes every dep replaceable — your tests don't need a real DB,
real Redis, real OpenAI key.

## Run

```bash
uvicorn 04_dependency_injection.app:app --reload --port 8000
```

```bash
# 401 — missing API key
curl -i http://localhost:8000/secret

# 200 — header provided
curl -i -H 'X-API-Key: secret-key' http://localhost:8000/secret

# pagination with defaults
curl 'http://localhost:8000/items'

# filters + pagination together
curl 'http://localhost:8000/search?q=laptop&tag=apple&tag=m3&limit=5'

# admin router — protected at the router level
curl -i http://localhost:8000/admin/stats
curl -i -H 'X-API-Key: secret-key' http://localhost:8000/admin/stats
```

## yield-based teardown

```python
async def get_db():
    db = make_db()
    try:
        yield db
    finally:
        db.close()
```

Teardown runs **after** the response is sent — perfect for closing
connections, removing temp files, releasing locks.

## Exercises

1. Write a `current_user(api_key: ApiKey) -> User` dep. Use it in three
   different routes. Notice that `require_api_key` only runs once per
   request even though `current_user` *also* depends on it.
2. Add a dep that returns a `httpx.AsyncClient` (yield-based, closed in
   `finally`). Reuse it across endpoints.
3. Write a test that overrides `get_db` with a stub.
