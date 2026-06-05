# 22 — Async databases (SQLAlchemy 2.x)

In production, your DB is the first place to go async. A blocking
DB call freezes an async worker just like any other blocking call.

## Modern SQLAlchemy stack

- **engine** = `create_async_engine(URL)` — manages a connection pool.
- **session factory** = `async_sessionmaker(engine, expire_on_commit=False)`.
- **session** = unit of work; opened per request via a `yield` dep.
- **ORM** = declarative models with type hints (`Mapped[...]`).

## Run

```bash
uvicorn 22_database_async.app:app --reload --port 8000

curl -X POST http://localhost:8000/notes \
  -H 'Content-Type: application/json' -d '{"title":"hi","body":"hello world"}'
curl http://localhost:8000/notes
```

## The yield dep is the right abstraction

```python
async def get_session():
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
```

- Auto-commit on success.
- Auto-rollback on failure.
- One session per request — no shared state across requests.

## Driver matters

- `sqlite+aiosqlite` — great for local dev, **single writer**.
- `postgresql+asyncpg` — production. Add `pool_size`, `max_overflow`.
- `mysql+aiomysql` — also works.

Just change `DATABASE_URL`.

## Anti-patterns

- **Sync** SQLAlchemy 1.x inside `async def` — blocks the loop. Use
  `run_in_threadpool` or migrate.
- A single global `Session` shared across requests — race conditions.
- Long-running transactions with external IO inside — releases connections
  back to the pool slowly. Keep transactions short.

## Migrations

We didn't include Alembic to keep things small. In production:

```bash
pip install alembic
alembic init migrations
# edit env.py to use our async engine
alembic revision --autogenerate -m "create notes"
alembic upgrade head
```

## Exercises

1. Add an index on `Note.title` and measure search vs scan timing.
2. Add a `notes_tags` many-to-many. Practise `selectinload` to avoid
   N+1 queries.
3. Convert the route layer into a small repository class
   (`NotesRepo`) used by the handler — keeps DB logic out of the API.
