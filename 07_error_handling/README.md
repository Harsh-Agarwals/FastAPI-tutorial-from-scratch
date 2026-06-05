# 07 — Error Handling

Errors are part of your API. Decide on **one shape** and use it
everywhere. We pick **RFC 7807 — Problem Details for HTTP APIs**:

```json
{
  "type": "about:blank",
  "title": "InsufficientBalance",
  "status": 422,
  "code": "insufficient_balance",
  "detail": "Need 200, have 100",
  "instance": "http://localhost:8000/transfer"
}
```

Stable fields:
- `status` — HTTP status (also in the response status line).
- `code` — short, machine-readable identifier. Clients switch on this.
- `title` — short human label.
- `detail` — long human message.
- `instance` — the URL where it happened.
- `errors` — for validation failures, the per-field list.

## Run + try

```bash
uvicorn 07_error_handling.app:app --reload --port 8000

# Domain error — 422 with code=insufficient_balance
curl -s -X POST http://localhost:8000/transfer \
  -H 'Content-Type: application/json' \
  -d '{"from_account":"acc-1","to_account":"acc-2","amount":9999}' | jq

# Domain error — 404 not_found
curl -s -X POST http://localhost:8000/transfer \
  -H 'Content-Type: application/json' \
  -d '{"from_account":"acc-xxx","to_account":"acc-2","amount":1}' | jq

# Validation error — 422 validation_error (Pydantic)
curl -s -X POST http://localhost:8000/transfer \
  -H 'Content-Type: application/json' \
  -d '{"from_account":"acc-1","to_account":"acc-2","amount":-1}' | jq

# Server crash — 500 internal_error
curl -i http://localhost:8000/boom
```

## Principles

1. **Never leak stack traces.** Log them server-side. Return a generic
   500 to the client. Include a request id (chapter 06) so support can
   correlate.
2. **One envelope.** Clients have one error parser instead of N.
3. **Raise *domain* errors, not HTTP errors.** The mapping to HTTP is
   the boundary's job. Your business code says
   `raise InsufficientBalance(...)`, not `raise HTTPException(422, ...)`.
4. **Validation errors are still errors.** Map them to the same envelope.
5. **Stable `code` field.** Clients should switch on `code`, not on
   `detail` text — text is for humans.

## Order of resolution

When the same exception could match multiple handlers (e.g. a custom
subclass of `HTTPException`), FastAPI picks the **most specific**.
`Exception` is the fallback — only triggers if nothing else matches.

## Edge cases

- `HTTPException(detail=<dict>)` returns a dict in `detail` — fine for
  rich errors but breaks our string-typed `detail`. Decide one way.
- Async generators that raise in middle of streaming → handled
  differently; the response is partially sent and you can't add headers.
- During request body parsing, an error fires *before* your handler
  runs. The `RequestValidationError` handler catches it.

## Exercises

1. Add a `Conflict` domain error mapped to 409 with `code=conflict`.
2. Add a request id to every problem response (read it from
   `request.state.request_id` once you have a middleware).
3. Add a "developer mode" toggled by `APP_ENV=local` that includes the
   exception class name in 500 responses — useful while iterating.
