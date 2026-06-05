# Notes — Chapter 03

## Pydantic v2 vs v1 (gotchas)

- `@validator` → `@field_validator` (with `@classmethod`).
- `class Config:` → `model_config = ConfigDict(...)`.
- `.dict()` → `.model_dump()`. `.json()` → `.model_dump_json()`.
- `parse_obj` → `model_validate`.

## Performance

- Pydantic v2 core is in **Rust**. Validation is ~10–50x faster than v1.
- Validation cost is real on hot paths — don't validate the same object twice.
- For maximum perf in internal flows, you can construct models with
  `Model.model_construct(...)` to skip validation (dangerous; use sparingly).

## Best practices

- **Public API model ≠ DB model.** Always separate.
- **Never put secrets on the response model.** `exclude=True` is a safety net.
- **Prefer `EmailStr`, `HttpUrl`, `UUID4`** over `str`. The type *is* the check.
- **For list inputs, use `conlist` / `Field(min_length=...)` to bound size.**
  Otherwise a client can DoS you with a giant array.
