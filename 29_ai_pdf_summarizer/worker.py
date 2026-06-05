"""
Capstone worker. Consumes jobs from Redis, parses PDFs, summarises
chunks via the LLM, and publishes progress + tokens.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import pathlib
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import redis.asyncio as aioredis

# Reach into sibling chapters via importlib (digit-prefix folders are not
# valid `import` keyword targets, but importlib resolves them fine).
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

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = "queue:summarize_pdf"
JOB_PREFIX = "summary:job:"
CHANNEL_PREFIX = "summary:tokens:"
CACHE_PREFIX = "summary:cache:"

CORES = max(1, (os.cpu_count() or 2) - 1)
MAX_CONCURRENT_LLM = 5

_stop = False


def _on_sig(*_):
    global _stop
    _stop = True


def _parse_chunks(path: str) -> list[str]:
    return [c.text for c in chunk_text(extract_pages(pathlib.Path(path).read_bytes()))]


async def _update(r, job_id, **fields):
    await r.hset(JOB_PREFIX + job_id, mapping={k: json.dumps(v) for k, v in fields.items()})


async def _publish(r, job_id, event: str, **data):
    await r.publish(CHANNEL_PREFIX + job_id, json.dumps({"event": event, "data": data}))


async def _cache_get(r, key) -> str | None:
    return await r.get(CACHE_PREFIX + key)


async def _cache_set(r, key, value):
    await r.set(CACHE_PREFIX + key, value, ex=24 * 3600)


async def handle(r, pool: ProcessPoolExecutor, item: dict) -> None:
    job_id = item["job_id"]
    path = item["path"]
    loop = asyncio.get_running_loop()
    llm = get_llm()
    sem = asyncio.Semaphore(MAX_CONCURRENT_LLM)

    await _update(r, job_id, status="parsing", started_at=time.time())
    await _publish(r, job_id, "status", status="parsing")

    chunks = await loop.run_in_executor(pool, _parse_chunks, path)
    if not chunks:
        await _update(r, job_id, status="failed", error="no text in pdf")
        await _publish(r, job_id, "status", status="failed", error="no text in pdf")
        return

    await _update(r, job_id, status="summarising", chunks_total=len(chunks), chunks_done=0)
    await _publish(r, job_id, "status", status="summarising", chunks_total=len(chunks))

    async def summarise_one(idx: int, text: str) -> str:
        key = hashlib.sha256(text.encode()).hexdigest()[:24]
        cached = await _cache_get(r, key)
        if cached:
            await _publish(r, job_id, "chunk_done", index=idx, cached=True)
            return cached
        async with sem:
            res = await call_with_retry(llm, build_prompt(text, "concise"))
        await _cache_set(r, key, res["text"])
        await _publish(r, job_id, "chunk_done", index=idx, cached=False)
        return res["text"]

    partials: list[str] = []
    done = 0
    for coro in asyncio.as_completed([summarise_one(i, t) for i, t in enumerate(chunks)]):
        partials.append(await coro)
        done += 1
        await _update(r, job_id, chunks_done=done)

    # Reduce.
    reduce_in = "\n".join(f"- {s}" for s in partials)
    final = await call_with_retry(llm, build_prompt(reduce_in, "concise"))
    await _update(r, job_id, status="done", summary=final["text"], finished_at=time.time())
    await _publish(r, job_id, "summary", summary=final["text"])
    await _publish(r, job_id, "status", status="done")


async def main():
    r = aioredis.from_url(REDIS_URL, decode_responses=True)
    pool = ProcessPoolExecutor(max_workers=CORES)
    print("[worker] capstone up. cores:", CORES)
    try:
        while not _stop:
            popped = await r.blpop(QUEUE, timeout=2)
            if popped is None:
                continue
            _key, raw = popped
            item = json.loads(raw)
            try:
                await handle(r, pool, item)
            except Exception as e:  # noqa: BLE001
                jid = item.get("job_id", "?")
                await _update(r, jid, status="failed", error=repr(e))
                await _publish(r, jid, "status", status="failed", error=repr(e))
                print("[worker] failed", jid, e)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        await r.close()
        print("[worker] bye")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _on_sig)
    signal.signal(signal.SIGTERM, _on_sig)
    asyncio.run(main())
