# Notes — Chapter 04

## Why DI matters in production

- **Testability**: every external dep is overridable.
- **Lifecycle**: yield-style deps handle setup/teardown deterministically.
- **Composability**: deps depend on deps; the tree is built per-request.
- **Performance**: request-scoped caching avoids repeated work.

## Common pitfalls

- Putting heavy work in a dep that runs on every request: it does. Cache.
- `yield`ing after a blocking call: if your DB driver is sync, you are
  blocking the event loop. Use async drivers (chapter 22).
- Confusing **dependency** with **middleware**: middleware runs for *all*
  routes; deps run only where declared. Prefer deps when possible.

## Sync vs async deps

You can mix. FastAPI runs sync deps in a threadpool so they don't block.
But that's another layer; prefer `async def` for IO deps.

## Class deps vs function deps

- Use a function dep when the value is data (a dict, a user).
- Use a class dep when the value carries methods or holds resources.

## Debugging

Add `log.debug("entering dep")` inside a dep to trace the resolution
order. The order is: leaves first, then upward, then the handler.
