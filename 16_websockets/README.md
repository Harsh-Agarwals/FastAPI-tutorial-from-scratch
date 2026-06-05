# 16 — WebSockets (fake AI streaming chat)

WebSockets are HTTP's bidirectional upgrade. Two things make them
worth learning for AI backends:

1. **Token streaming** — show output as it arrives instead of after.
2. **Realtime progress** — push job updates without polling.

## Run

```bash
uvicorn 16_websockets.app:app --reload --port 8000
```

Open <http://localhost:8000/> — the page is the chat client. Open
several tabs and chat across them via `/ws/room`.

CLI alternative with `wscat` (or `websocat`):
```bash
wscat -c ws://localhost:8000/ws/chat
> hello
< {"event":"start"}
< {"event":"token","data":"You "}
...
```

## The lifecycle

```
client                       server
  |--- HTTP Upgrade ----------->|
  |<-- 101 Switching Protocols--|
  |     full duplex now          |
  |--- send_text -------------->|
  |<-- send_json --(many)-------|
  |--- close ------------------>|
```

In FastAPI:

```python
@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    try:
        while True:
            data = await socket.receive_text()
            await socket.send_text(reply(data))
    except WebSocketDisconnect:
        return  # don't re-raise
```

## Streaming tokens vs polling

For long LLM answers, streaming gives users feedback within ~200 ms
instead of waiting 10+ seconds. Pattern:

```python
async for token in llm.stream(prompt):
    await ws.send_json({"event": "token", "data": token})
```

## Connection manager pattern

For broadcast (chat rooms, live dashboards, AI job progress):

- Keep a `set[WebSocket]` of active connections (per-room if needed).
- Use a lock around modifications.
- On `send_json` failure, silently drop the dead socket.

## Production realities

- **Sticky sessions or pub/sub for multi-instance broadcasts.** Two
  servers? They each have their own `set`. Use Redis pub/sub to
  broadcast across instances (chapter 20).
- **Auth at connect time.** Read a token from a query param or the
  `Sec-WebSocket-Protocol` header before `await ws.accept()`.
- **Heartbeats.** Send a ping every 20s; close idle sockets to free
  resources.
- **Origin / CSRF.** Restrict `Origin` to your domains.

## Exercises

1. Add a `/ws/jobs/{id}` that streams job progress from the chapter 9
   in-memory job store. Use a `JOB_DONE` event to close.
2. Add a per-connection auth check via a query param `?token=...`.
3. Make the chat room scale by sharing messages through Redis pub/sub
   (after chapter 20).
