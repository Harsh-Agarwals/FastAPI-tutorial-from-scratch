"""
Chapter 16 — WebSockets — fake AI streaming chat.

We implement:
- a single-client WS endpoint that streams "tokens" with delays
- a small connection manager for broadcasting
- correct disconnect handling
- a tiny HTML chat UI served at "/" so you can test in a browser

Run:
    uvicorn 16_websockets.app:app --reload --port 8000
    # then open http://localhost:8000/  in your browser
"""
from __future__ import annotations

import asyncio
import random
from typing import Iterable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI(title="Chapter 16 — WebSockets")


# --- Fake LLM token stream ----------------------------------------------------
async def fake_llm_stream(prompt: str) -> Iterable[str]:
    """Yield tokens with realistic-feeling latency."""
    words = (
        f"You said: '{prompt[:40]}'. Here is a streamed pretend answer "
        "that arrives one chunk at a time, like a real LLM call."
    ).split()
    for w in words:
        await asyncio.sleep(random.uniform(0.05, 0.2))
        yield w + " "


# --- Single-client streaming endpoint ----------------------------------------
@app.websocket("/ws/chat")
async def chat(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            # Wait for a user message
            prompt = await ws.receive_text()
            # Tell the client we're about to stream
            await ws.send_json({"event": "start"})
            # Stream tokens; allow the client to interrupt by disconnecting
            async for token in fake_llm_stream(prompt):
                await ws.send_json({"event": "token", "data": token})
            await ws.send_json({"event": "end"})
    except WebSocketDisconnect:
        # Client closed the socket. Important: silently exit the handler;
        # do NOT raise. Any background tasks we created should be cancelled.
        return


# --- Broadcast: many clients receive the same message ------------------------
class ConnectionManager:
    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.discard(ws)

    async def broadcast(self, msg: dict) -> None:
        async with self._lock:
            conns = list(self._conns)
        # Send concurrently; ignore dead sockets.
        await asyncio.gather(*(self._safe_send(c, msg) for c in conns))

    @staticmethod
    async def _safe_send(ws: WebSocket, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            pass


manager = ConnectionManager()


@app.websocket("/ws/room")
async def room(ws: WebSocket) -> None:
    await manager.connect(ws)
    try:
        await manager.broadcast({"event": "join", "count": len(manager._conns)})
        while True:
            text = await ws.receive_text()
            await manager.broadcast({"event": "msg", "text": text})
    except WebSocketDisconnect:
        await manager.disconnect(ws)
        await manager.broadcast({"event": "leave", "count": len(manager._conns)})


# --- Minimal HTML client so you can play without any frontend setup ----------
PAGE = """
<!doctype html>
<title>Chapter 16 — WS chat</title>
<style>body{font-family:system-ui;max-width:680px;margin:2em auto}
#out{white-space:pre-wrap;background:#f6f8fa;padding:1em;border-radius:8px;min-height:120px}
input{width:100%;padding:.6em;font-size:1em}</style>
<h1>WS chat</h1>
<p>Open multiple tabs to see streaming.</p>
<div id=out></div>
<input id=in placeholder="Type a prompt, press Enter">
<script>
const out = document.getElementById('out');
const inp = document.getElementById('in');
const ws  = new WebSocket('ws://' + location.host + '/ws/chat');
ws.onmessage = ev => {
  const m = JSON.parse(ev.data);
  if (m.event === 'start') out.textContent += '\\n> ';
  if (m.event === 'token') out.textContent += m.data;
};
inp.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    out.textContent += '\\nYou: ' + inp.value;
    ws.send(inp.value);
    inp.value = '';
  }
});
</script>
"""


@app.get("/")
def index() -> HTMLResponse:
    return HTMLResponse(PAGE)
