# 17 — Streaming responses

Three flavours, same idea: the response body arrives in pieces.

| Format    | Best for                                | Client          |
|-----------|-----------------------------------------|-----------------|
| chunked text | naive token stream                  | `curl -N`       |
| **SSE**   | LLM token streams to the browser        | `EventSource`   |
| **NDJSON**| API-to-API streams (Ollama, Anthropic)  | line-delimited  |

We do NOT use HTTP/2 `Server Push` (deprecated). For chat-like
back-and-forth you still want WebSockets (chapter 16).

## Run

```bash
uvicorn 17_streaming_responses.app:app --reload --port 8000
curl -N http://localhost:8000/stream/text
curl -N http://localhost:8000/stream/sse
curl -N http://localhost:8000/stream/ndjson
```

Or open <http://localhost:8000/> for the SSE demo in a browser.

## SSE wire format in one shot

```
event: token
data: {"token":"Hello"}

event: token
data: {"token":"world"}

event: end
data: {}
```

- Records are separated by **blank line**.
- Each line starts with `event:`, `data:`, `id:`, or `:` (comment).
- `event:` is optional (default = "message").

## Client disconnect

The single most-forgotten pattern in streaming endpoints:

```python
async def gen():
    async for tok in upstream():
        if await request.is_disconnected():
            return                      # stop producing — save CPU + API $
        yield tok
```

Without this you keep paying OpenAI even after the user closes the tab.

## Proxies / nginx

If you serve behind nginx, disable buffering for streamed responses:

```
proxy_http_version 1.1;
proxy_set_header Connection '';
proxy_buffering off;
chunked_transfer_encoding on;
```

We also send `X-Accel-Buffering: no` from the app as a hint.

## Exercises

1. Add a `?token_delay_ms=...` query param so you can simulate fast vs
   slow streams during development.
2. Add a hard timeout that aborts after 30s of streaming.
3. Replace the fake generator with a real `httpx` streamed call to an
   upstream NDJSON endpoint, forwarding chunks downstream.
