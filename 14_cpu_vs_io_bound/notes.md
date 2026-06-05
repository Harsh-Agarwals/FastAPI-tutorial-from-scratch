# Notes — Chapter 14

## Amdahl's Law in one line

If 80% of your time is in the parallelisable part, max speedup is 5×,
no matter how many cores.

## Pickle overhead

Processes communicate through serialised bytes. Small args are fine;
big tensors are not. For real ML work, prefer:
- shared memory (`multiprocessing.shared_memory`)
- numpy memmap
- a dedicated inference server with batched RPC

## Async + processes in FastAPI

The recipe we'll reuse: handler is `async def`, it dispatches CPU work
through `loop.run_in_executor(process_pool, fn, args)`. The loop is
free; cores are busy. Best of both worlds.

## Profiling

`py-spy top --pid <uvicorn pid>` is the quickest way to find out
whether your handler is *actually* IO-bound or CPU-bound. Don't guess.
