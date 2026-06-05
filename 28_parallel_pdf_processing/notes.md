# Notes — Chapter 28

## Cost shape

- Map: N small LLM calls. Cheap each, but it's N×.
- Reduce: 1 medium call. Usually fine.

If cost matters more than latency, do **refine** (sequential) instead of
map-reduce. Latency matters more? Stick with map-reduce.

## Failure handling

If 1 of 50 chunks fails after retries: do you fail the whole job or
return a partial summary? Be explicit. Real systems usually warn the
user and proceed.

## Quality tip

Add a **per-chunk header** like "(page 5/12 of `report.pdf`)" to give
the LLM positional context. Improves coherence in the final summary.

## Token accounting

Real production: sum `tokens_in`+`tokens_out` across all calls and log
it. Per-document cost surprises are common.
