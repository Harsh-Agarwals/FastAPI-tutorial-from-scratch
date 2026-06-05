# Notes — Chapter 12

## The GIL in one sentence

CPython's Global Interpreter Lock guarantees that only one thread
executes Python bytecode at a time. C extensions (NumPy, lxml, etc)
can release the GIL while doing native work.

## Future of the GIL

PEP 703 (the "free-threaded build") is an experimental no-GIL CPython
in 3.13+. Until it lands as default, design around the GIL.

## Practical rules

- Use threads for **sleep / network / disk** sync libraries.
- Use processes for **pure Python CPU work**.
- Use **async** for high-fanout IO with native async libs (best of all).
- For numeric crunching, push the loop into NumPy / pandas / Rust.

## Daemon threads vs futures

Prefer `concurrent.futures.ThreadPoolExecutor` over raw `threading.Thread`
in services — bounded pool, futures with results, easy cancellation.

## Avoid global state across threads

If you absolutely must share state, prefer:
- `queue.Queue` (thread-safe by design)
- atomic operations (one-line `count.value` if you use `multiprocessing.Value`)
- locks held for the shortest possible window
