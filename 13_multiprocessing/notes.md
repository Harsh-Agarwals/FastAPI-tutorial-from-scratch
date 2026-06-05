# Notes — Chapter 13

## Start methods

- `fork` (Linux default): cheap, but copies the parent's state. Plays
  badly with threads / DB pools opened pre-fork.
- `spawn` (macOS/Windows default): clean slate, but imports re-run.
- `forkserver`: hybrid; expensive once, cheap thereafter.

In FastAPI, prefer `spawn` for safety in production:

```python
import multiprocessing as mp
mp.set_start_method("spawn", force=True)
```

## Don't fork after opening DB / Redis pools

Connection pools opened **before** fork become invalid in children.
Open them **per process** instead (lifespan + process-local globals).

## When the GIL truly hurts you

Pure-Python regex over a 50 MB document. Pure-Python tokenisation.
Loops doing math. These get N× faster on N cores with processes.

If you can replace the inner loop with NumPy / Rust / Cython, that's
usually better than multiprocessing.

## Memory: COW caveat

On Linux + fork, child processes share read-only memory until they
write. Touching pages copies them. Long-running workers can quietly
become memory-heavy.
