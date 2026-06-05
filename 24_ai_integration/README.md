# 24 — AI Integration (the patterns, not the vendor)

Real AI services are 10% "call the model" and 90% the glue around it:
retries, timeouts, batching, caching, fallback. This chapter is the
glue.

## Design: client interface, not vendor lock-in

```python
class LLMClient(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int = 200) -> dict: ...
```

The rest of your code talks to `LLMClient`. You can swap OpenAI for
Anthropic, Bedrock, Ollama, or your `MockLLMClient` without touching
handlers or tests.

## Run

```bash
uvicorn 24_ai_integration.app:app --reload --port 8000

curl -X POST http://localhost:8000/summarize \
  -H 'Content-Type: application/json' \
  -d '{"text":"the quick brown fox jumps over the lazy dog ... long article", "style":"bullet"}'

# Batch
curl -X POST http://localhost:8000/summarize-batch \
  -H 'Content-Type: application/json' \
  -d '[{"text":"a"},{"text":"b"},{"text":"c"}]'
```

By default it uses `MockLLMClient` (no API key needed). Set
`OPENAI_API_KEY` in `.env` and `pip install openai` to use the real one.

## Patterns explained

### Retries with exponential backoff

`tenacity` retries only on **transient** errors (`HTTPError`, timeout).
We **don't** retry 4xx — those will fail forever. Exponential backoff
prevents thundering herd on a flaky upstream.

```python
AsyncRetrying(
    retry=retry_if_exception_type(RETRY_ON),
    wait=wait_exponential(multiplier=0.2, max=3.0),
    stop=stop_after_attempt(4),
)
```

### Timeouts at every layer

- per-request timeout on the HTTP call
- per-job timeout in your queue (chapter 21)
- per-handler timeout via `asyncio.timeout`

Never trust the upstream to time out.

### Batching

For embeddings + small completions, batch many items into one call.
You amortise overhead and stay under per-RPM limits.

### Prompt templates

Keep prompts in **one place** (a module / file), not scattered across
handlers. Versioning prompts becomes possible. Tests become possible.

### Caching

A hash of `(model, prompt)` → answer is one of the highest-leverage
optimisations in any AI service. We do it inline; the real version
lives in chapter 19.

## Common pitfalls

- **Retrying 4xx**: wastes tokens, hides bugs.
- **Sync OpenAI SDK calls** inside async handlers — freezes the loop.
  Use `AsyncOpenAI`.
- **No prompt versioning**: when answers change, you cannot tell if it
  was the model or your prompt.
- **No per-tenant budget**: one customer can rack up your bill.
  Combine with chapter 18 (rate limit) and chapter 19 (cache).

## Exercises

1. Add a `provider` query param that picks between `openai` and `mock`.
2. Add a "fallback chain": try OpenAI → on failure, try Anthropic →
   on failure, return a graceful 503.
3. Track per-prompt token use via a metric `ai_tokens_total{kind,model}`.
