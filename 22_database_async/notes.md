# Notes — Chapter 22

## Pool sizing for Postgres

A rule of thumb: `pool_size + max_overflow ≤ postgres max_connections / workers / replicas`.
Too high and you starve Postgres; too low and you queue requests.

## `expire_on_commit=False`

After commit, SQLAlchemy by default *expires* all objects. Subsequent
attribute access triggers a new SELECT. With async, that SELECT can
fire during JSON serialisation — which is too late to await.
`expire_on_commit=False` keeps loaded attributes cached.

## N+1 queries

If a handler returns a list of notes with `note.tags`, you'll get one
extra query per row. Use `selectinload(Note.tags)` to eager-load.

## Transaction scope

Keep transactions small. If you call OpenAI inside a transaction, the
connection stays open for seconds. Use a separate session for the LLM
result write.

## Testing

For tests, use `aiosqlite` with `:memory:` and create a fresh engine
per test. With Postgres tests, use `pytest-postgresql` or a Docker
container fixture.
