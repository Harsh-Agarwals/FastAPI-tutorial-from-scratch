"""
Chapter 17 — StreamingResponse (chunked) + Server-Sent Events.

For one-way streams (server → client), SSE is the cheapest option:
- Plain HTTP. Works through reverse proxies easily.
- Built-in browser support via `EventSource`.
- No special client libraries.

We also show NDJSON streaming — popular for AI APIs (Anthropic, Ollama).

Run:
    uvicorn 17_streaming_responses.app:app --reload --port 8000

In one terminal:
    curl -N http://localhost:8000/stream/sse
    curl -N http://localhost:8000/stream/ndjson
"""
from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI(title="Chapter 17 — Streaming Responses")


async def fake_tokens(prompt: str = "hello") -> AsyncIterator[str]:
    """Simulates an LLM generating tokens one at a time."""
    words = (f"Streaming reply to '{prompt}'. " * 6).split()
    for w in words:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        yield w


# --- Plain chunked text -----------------------------------------------------
@app.get("/stream/text")
async def text_stream(request: Request) -> StreamingResponse:
    async def gen():
        async for w in fake_tokens():
            if await request.is_disconnected():
                # The client closed the connection; stop producing tokens.
                return
            yield (w + " ").encode()

    return StreamingResponse(gen(), media_type="text/plain")


# --- Server-Sent Events (SSE) ----------------------------------------------
@app.get("/stream/sse")
async def sse(request: Request, prompt: str = "hi") -> StreamingResponse:
    """
    SSE wire format (one event per record):
        event: token
        data: hello
        \\n

    Lines starting with `:` are comments — used here as keep-alives.
    """
    async def gen():
        yield b": connected\n\n"          # comment line as initial keep-alive
        async for w in fake_tokens(prompt):
            if await request.is_disconnected():
                return
            payload = json.dumps({"token": w})
            yield f"event: token\ndata: {payload}\n\n".encode()
        yield b"event: end\ndata: {}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering when proxied
        },
    )


# --- NDJSON: one JSON object per line ---------------------------------------
@app.get("/stream/ndjson")
async def ndjson(request: Request, prompt: str = "hi") -> StreamingResponse:
    async def gen():
        async for w in fake_tokens(prompt):
            if await request.is_disconnected():
                return
            yield (json.dumps({"token": w}) + "\n").encode()

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# --- Tiny browser demo using EventSource -----------------------------------
PAGE = """
<!doctype html><title>SSE demo</title>
<style>body{font-family:system-ui;max-width:600px;margin:2em auto}
#out{white-space:pre-wrap;background:#f6f8fa;padding:1em;border-radius:8px;min-height:120px}</style>
<h1>SSE token stream</h1>
<div id=out></div>
<script>
const out = document.getElementById('out');
const es = new EventSource('/stream/sse?prompt=hello+SSE');
es.addEventListener('token', ev => {
  const m = JSON.parse(ev.data);
  out.textContent += m.token + ' ';
});
es.addEventListener('end', () => { es.close(); out.textContent += '\\n--end--'; });
</script>
"""


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)
