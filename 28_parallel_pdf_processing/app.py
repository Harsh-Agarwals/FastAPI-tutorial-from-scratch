"""
Chapter 28 — Parallel PDF summarisation.

The realistic AI workload:
  1. parse PDF              (CPU bound)        → process pool
  2. summarize each chunk   (IO bound to LLM)  → asyncio + semaphore
  3. combine partial summaries into a final one

We assemble the patterns from chapters 13 (process pool) + 11 (semaphore)
+ 24 (LLM client) into one endpoint.

Run:
    uvicorn 28_parallel_pdf_processing.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile

# Re-use existing modules from sibling chapters. We use importlib because
# Python's `import` keyword cannot reference a package whose folder name
# starts with a digit (`27_pdf_processing`); importlib has no such limit.
import importlib

_REPO_ROOT = str(pathlib.Path(__file__).parent.parent.resolve())
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ch27 = importlib.import_module("27_pdf_processing.app")
_ch24 = importlib.import_module("24_ai_integration.app")
extract_pages = _ch27.extract_pages
chunk_text = _ch27.chunk_text
get_llm = _ch24.get_llm
build_prompt = _ch24.build_prompt
call_with_retry = _ch24.call_with_retry

from concurrent.futures import ProcessPoolExecutor

CORES = max(1, (os.cpu_count() or 2) - 1)
MAX_PAGES = 200            # safety guard
MAX_CONCURRENT_LLM = 5     # be nice to upstream


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = ProcessPoolExecutor(max_workers=CORES)
    try:
        yield
    finally:
        app.state.pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title="Chapter 28 — Parallel PDF Summarisation", lifespan=lifespan)


# CPU step that runs in a worker process. Top-level for pickling.
def _parse_and_chunk(data: bytes) -> list[dict]:
    pages = extract_pages(data)
    if len(pages) > MAX_PAGES:
        raise ValueError(f"PDF too large: {len(pages)} pages > {MAX_PAGES}")
    return [c.__dict__ for c in chunk_text(pages)]


@app.post("/summarize-pdf")
async def summarize_pdf(file: UploadFile = File(...)) -> dict:
    if not file.content_type or "pdf" not in file.content_type:
        raise HTTPException(415, "Send a PDF")
    data = await file.read()
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "Not a PDF")

    # 1. CPU work: parse + chunk in a worker process.
    loop = asyncio.get_running_loop()
    try:
        chunks = await loop.run_in_executor(app.state.pool, _parse_and_chunk, data)
    except ValueError as e:
        raise HTTPException(413, str(e))
    except Exception as e:
        raise HTTPException(422, f"Parse failed: {e}")

    if not chunks:
        raise HTTPException(422, "No text extracted")

    # 2. IO work: summarize each chunk concurrently with bounded concurrency.
    llm = get_llm()
    sem = asyncio.Semaphore(MAX_CONCURRENT_LLM)

    async def summarize_chunk(text: str) -> str:
        async with sem:
            res = await call_with_retry(llm, build_prompt(text, "concise"))
            return res["text"]

    partial_summaries = await asyncio.gather(*(summarize_chunk(c["text"]) for c in chunks))

    # 3. Reduce step — feed all partials back into the LLM for a final summary.
    reduce_input = "\n".join(f"- {s}" for s in partial_summaries)
    final = await call_with_retry(llm, build_prompt(reduce_input, "concise"))

    return {
        "chunks": len(chunks),
        "partials": partial_summaries,
        "summary": final["text"],
        "model": final["model"],
        "tokens_in": final["tokens_in"],
        "tokens_out": final["tokens_out"],
    }
