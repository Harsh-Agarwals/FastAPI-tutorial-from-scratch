# Notes — Chapter 17

## When to use what

- Browser, one-way → SSE
- Backend-to-backend, one-way → NDJSON
- Two-way → WebSocket
- Big binary file → use `FileResponse` or signed S3 URLs, not a stream
  through your app

## Headers that matter

- `Cache-Control: no-cache` — proxies must not cache a live stream.
- `Connection: keep-alive` — make the TCP connection reusable.
- `X-Accel-Buffering: no` — turn off nginx buffering.
- `Content-Type: text/event-stream` — magic content type for SSE.

## Heartbeats

Send a comment line (`:keepalive\\n\\n`) every ~15 seconds so proxies
don't close idle connections.

## Backpressure

`StreamingResponse` yields are blocked by the OS socket buffer when the
client is slow. That gives natural backpressure — your generator pauses
on `yield` until the bytes are accepted.
