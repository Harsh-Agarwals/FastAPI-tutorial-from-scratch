# Notes — Chapter 16

## WebSocket vs Server-Sent Events (SSE)

- WebSocket: full duplex, harder load balancing, more libraries needed.
- SSE: one-way (server → client), trivial over HTTP. We use it in
  chapter 17 for the simpler streaming case.

For LLM token streaming where the client just listens, **SSE is
usually enough** and is much easier to operate. Use WebSocket when
you need bidirectional or many-event protocols (chat, collaborative).

## Backpressure on the wire

`ws.send_*` will block if the kernel buffer fills (slow client). That
is fine — it naturally slows down your producer. Avoid spawning
unbounded background tasks that all try to send.

## Disconnects

- Browser tab closed → `WebSocketDisconnect` (clean).
- Network down → may take TCP keepalive timeout (could be minutes).
  Use app-level pings.

## Scaling

- A uvicorn worker can hold tens of thousands of WS connections if
  they are mostly idle.
- For very high counts (millions), put a dedicated reverse proxy in
  front and consider a specialised gateway (Phoenix, ESH).
