# 28 — Parallel PDF Summarisation (the real pattern)

This is the map-reduce of AI. We combine three earlier chapters:

| Stage         | Bound     | Strategy                             |
|---------------|-----------|--------------------------------------|
| Parse + chunk | CPU       | `ProcessPoolExecutor` (ch 13)        |
| Summarise N   | IO (LLM)  | `asyncio.gather` + `Semaphore` (ch 11)|
| Reduce        | IO (LLM)  | one final LLM call                   |

This is the **exact shape** Anthropic / OpenAI tools use for long-doc
summarisation under the hood.

## Run

```bash
uvicorn 28_parallel_pdf_processing.app:app --reload --port 8000

curl -F "file=@./sample.pdf;type=application/pdf" \
  http://localhost:8000/summarize-pdf | jq '{chunks, summary}'
```

## Why split parse from summarise?

- Parsing is CPU. Doing it in the event loop blocks every other request.
- Summarising is IO (LLM call). Doing it in a process pool is wasteful
  and re-pickles big strings.

Right tool, right thread.

## Why a Semaphore for LLM calls?

OpenAI rate-limits per minute. Unbounded `gather` over 50 chunks will:
- get 429 from the provider,
- and saturate your own httpx pool.

A `Semaphore(5)` caps concurrency without changing the rest of the code.

## Map-reduce summarisation

Each chunk gets a "concise" summary. The list of summaries is fed back
through the LLM for a final summary. Variants:

- **Hierarchical** — group partials → summary of summaries → final.
- **Refine** — process chunks sequentially, growing the summary.
- **Stuff** — only works for short docs that fit in one prompt.

## Edge cases

- Empty PDFs (no extractable text) → 422.
- Huge PDFs → reject early with `MAX_PAGES`.
- LLM fails on one chunk after retries → fail the whole call or
  return a partial result (your choice — be explicit).

## Exercises

1. Add per-chunk **caching** keyed on the chunk's hash. Re-summarising
   the same document should be free.
2. Stream partial summaries to the client over SSE (chapter 17) so the
   user sees progress.
3. Replace `gather` with `asyncio.as_completed` so the first chunks
   start streaming before the last finish.
