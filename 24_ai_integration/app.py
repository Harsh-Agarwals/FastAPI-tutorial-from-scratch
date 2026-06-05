"""
Chapter 24 — AI integration.

Pattern, not provider. We design the *shape* of an AI client:

- abstract `LLMClient` interface (so we can swap providers)
- `MockLLMClient` — works offline, deterministic, fast
- `OpenAIClient` — uncomment and add API key when ready
- retries with exponential backoff (tenacity)
- timeouts
- batching helper
- prompt builder (you should always have one)

Run:
    uvicorn 24_ai_integration.app:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
from typing import Protocol

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="Chapter 24 — AI Integration")


# ---------------------------------------------------------------------------
# Pydantic schemas — the public API stays stable even if we swap providers.
# ---------------------------------------------------------------------------
class SummarizeIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    style: str = Field(default="concise", pattern="^(concise|detailed|bullet)$")


class SummarizeOut(BaseModel):
    summary: str
    tokens_in: int
    tokens_out: int
    model: str
    cached: bool = False


# ---------------------------------------------------------------------------
# Provider interface — keeps the rest of the app decoupled from any vendor.
# ---------------------------------------------------------------------------
class LLMClient(Protocol):
    async def complete(self, prompt: str, *, max_tokens: int = 200) -> dict: ...


class MockLLMClient:
    """Pretends to be an LLM. Slight latency + occasional errors."""

    async def complete(self, prompt: str, *, max_tokens: int = 200) -> dict:
        await asyncio.sleep(random.uniform(0.05, 0.25))
        if random.random() < 0.1:  # 10% failure rate to exercise retry
            raise httpx.HTTPError("mock upstream blip")
        # Pretend summary: first 60 chars + word count.
        summary = (prompt.split("\n\n", 1)[-1])[:60].strip() + "…"
        words = prompt.split()
        return {
            "text": summary,
            "tokens_in": len(words),
            "tokens_out": len(summary.split()),
            "model": "mock-llm-1.0",
        }


class OpenAIClient:
    """
    Real OpenAI client. Uncomment after `pip install openai` and
    after setting OPENAI_API_KEY in your .env.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    async def complete(self, prompt: str, *, max_tokens: int = 200) -> dict:
        # raise NotImplementedError("uncomment and pip install openai")
        from openai import AsyncOpenAI  # type: ignore

        client = AsyncOpenAI(api_key=self.api_key)
        r = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=15,
        )
        usage = r.usage
        return {
            "text": r.choices[0].message.content,
            "tokens_in": usage.prompt_tokens,
            "tokens_out": usage.completion_tokens,
            "model": self.model,
        }


def get_llm() -> LLMClient:
    if OPENAI_API_KEY:
        return OpenAIClient(OPENAI_API_KEY, OPENAI_MODEL)
    return MockLLMClient()


# ---------------------------------------------------------------------------
# Prompt construction — keep prompts in code, not strings everywhere.
# ---------------------------------------------------------------------------
PROMPT_TEMPLATES = {
    "concise":  "Summarize the following in 2 sentences:\n\n{text}",
    "detailed": "Provide a detailed summary of the following:\n\n{text}",
    "bullet":   "Summarize the following as 5 bullet points:\n\n{text}",
}


def build_prompt(text: str, style: str) -> str:
    return PROMPT_TEMPLATES[style].format(text=text)


# ---------------------------------------------------------------------------
# Retry helper — only retry on *transient* errors, not bad-request 4xx.
# ---------------------------------------------------------------------------
RETRY_ON = (httpx.HTTPError, asyncio.TimeoutError)


async def call_with_retry(llm: LLMClient, prompt: str) -> dict:
    async for attempt in AsyncRetrying(
        reraise=True,
        retry=retry_if_exception_type(RETRY_ON),
        wait=wait_exponential(multiplier=0.2, max=3.0),
        stop=stop_after_attempt(4),
    ):
        with attempt:
            return await llm.complete(prompt)
    return {}  # unreachable


# ---------------------------------------------------------------------------
# Tiny in-process cache — see chapter 19 for the proper version.
# ---------------------------------------------------------------------------
_cache: dict[str, dict] = {}


def cache_key(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.post("/summarize", response_model=SummarizeOut)
async def summarize(payload: SummarizeIn) -> SummarizeOut:
    llm = get_llm()
    prompt = build_prompt(payload.text, payload.style)
    key = cache_key(prompt, OPENAI_MODEL if OPENAI_API_KEY else "mock-llm-1.0")

    if hit := _cache.get(key):
        return SummarizeOut(**hit, cached=True)

    try:
        result = await call_with_retry(llm, prompt)
    except Exception as e:
        raise HTTPException(502, f"upstream LLM failed: {e}")
    _cache[key] = {
        "summary": result["text"],
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "model": result["model"],
    }
    return SummarizeOut(**_cache[key])


@app.post("/summarize-batch", response_model=list[SummarizeOut])
async def summarize_batch(payloads: list[SummarizeIn]) -> list[SummarizeOut]:
    """Concurrent summaries, capped to avoid abusing upstream."""
    sem = asyncio.Semaphore(5)

    async def one(p):
        async with sem:
            return await summarize(p)

    return await asyncio.gather(*(one(p) for p in payloads))
