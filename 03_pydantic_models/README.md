# 03 — Pydantic Models, the right way

Pydantic v2 is doing more work in your API than any other library. The
patterns below pay back the time you spend learning them.

## Core ideas

1. **Separate models for Create / Read / Update.**
   You should never accept a `User` object that the DB will save, then
   send the *same* object back. A "Create" model never contains an `id`
   or `created_at`. A "Read" model never contains a `password`.

2. **`Field(...)` is your validation toolkit.**
   `min_length`, `max_length`, `ge`, `le`, `pattern`, `default_factory`,
   `alias`, `exclude`. Use them aggressively.

3. **`@field_validator` for single fields. `@model_validator(mode="after")`
   for cross-field rules** (e.g. `end > start`).

4. **`computed_field`** — derived values (e.g. `is_adult`). They appear
   in the JSON output without being stored.

5. **Discriminated unions** — clean polymorphism. Pydantic picks the
   right variant by reading a tag field.

6. **Aliases** — let your *internal* code stay snake_case while your
   *external* JSON stays camelCase. The two don't have to match.

## Run

```bash
uvicorn 03_pydantic_models.app:app --reload --port 8000
```

## Try it

```bash
# Note: camelCase fullName accepted thanks to aliases
curl -X POST http://localhost:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","fullName":"  Ada Lovelace  ","age":36,"password":"hunter12"}'

# The response uses camelCase too (response_model_by_alias=True)
curl http://localhost:8000/users/1

# Cross-field validation kicks in (422)
curl -X POST http://localhost:8000/date-range \
  -H 'Content-Type: application/json' \
  -d '{"start":"2025-01-02T00:00:00Z","end":"2025-01-01T00:00:00Z"}'

# Discriminated union picks CardPayment
curl -X POST http://localhost:8000/orders \
  -H 'Content-Type: application/json' \
  -d '{"amount_cents":1500,"payment":{"kind":"card","last4":"4242"}}'
```

## Why `exclude=True` matters

`password` is on the input model so we can read and (in real code)
hash it. But it must never appear in *any* response. `exclude=True`
plus a separate `UserRead` model makes that *impossible*, not just
"convention".

## Edge cases

- Sending `age: "30"` — Pydantic v2 will coerce, but you can set
  `model_config = ConfigDict(strict=True)` to refuse.
- Whitespace in `full_name`: stripped by `str_strip_whitespace=True`.
- Unknown extra fields are silently ignored by default. Want to reject?
  `model_config = ConfigDict(extra="forbid")`.
- `EmailStr` requires `email-validator` (already in our `requirements.txt`).

## Exercises

1. Add a `UserUpdate` model where every field is optional and use it
   with a `PATCH /users/{id}` endpoint. Use `model_dump(exclude_unset=True)`
   to apply only the fields the client actually sent.
2. Add a third payment variant `WalletPayment{ kind: "wallet", provider: ... }`.
3. Make `created_at` UTC-only by adding a `field_validator` that rejects
   naive datetimes.
4. Toggle `extra="forbid"` on `UserCreate` and see what happens with a
   `{"hax": 1, ...}` payload.
