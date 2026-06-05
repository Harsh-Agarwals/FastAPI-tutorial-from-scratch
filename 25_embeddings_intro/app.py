"""
Chapter 25 — Embeddings: intuition and a tiny working example.

What is an embedding?
- A function `text -> vector[float]` whose vectors are "close" for
  semantically similar texts.
- We use a tiny **mock embedder** that you can fully reason about:
  every text becomes a 16-d vector based on character counts.
  That is enough to learn the *shape* of an embedding pipeline.
- Replace with `text-embedding-3-small` (1536-d) when you want real.

Run:
    uvicorn 25_embeddings_intro.app:app --reload --port 8000
"""
from __future__ import annotations

import string
from typing import Iterable

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Chapter 25 — Embeddings")


# ---------------------------------------------------------------------------
# Mock embedder — a deterministic toy you can debug by hand.
#
# Vector = normalised counts of 16 selected ascii groups.
# ---------------------------------------------------------------------------
_BUCKETS = [
    "aeiou",                # vowels
    "bcdfghjklmnpqrstvwxyz",# consonants
    string.digits,
    " ",                    # spaces
    ".!?,",                 # sentence punctuation
    ":;'\"-",               # other punctuation
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "()[]{}",
] + [c for c in "tfsoa0123nh"]  # add a few single-char buckets to reach 16

assert len(_BUCKETS) == 16


def mock_embed(text: str) -> np.ndarray:
    v = np.zeros(16, dtype=np.float32)
    if not text:
        return v
    for i, bucket in enumerate(_BUCKETS):
        v[i] = sum(c in bucket for c in text)
    # L2-normalise so cosine sim ∈ [-1, 1].
    norm = float(np.linalg.norm(v))
    return v / norm if norm else v


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # since a, b are L2-normalised


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
class EmbedIn(BaseModel):
    texts: list[str]


class EmbedOut(BaseModel):
    dim: int
    vectors: list[list[float]]


@app.post("/embed", response_model=EmbedOut)
def embed(payload: EmbedIn) -> EmbedOut:
    vs = [mock_embed(t).tolist() for t in payload.texts]
    return EmbedOut(dim=16, vectors=vs)


class SimIn(BaseModel):
    a: str
    b: str


class SimOut(BaseModel):
    a: str
    b: str
    cosine_similarity: float


@app.post("/similarity", response_model=SimOut)
def similarity(payload: SimIn) -> SimOut:
    return SimOut(
        a=payload.a,
        b=payload.b,
        cosine_similarity=cosine(mock_embed(payload.a), mock_embed(payload.b)),
    )


# A toy corpus + nearest-neighbour query for intuition.
CORPUS = [
    "FastAPI is great for building APIs.",
    "Python is a programming language.",
    "I had pasta for dinner.",
    "Embeddings turn text into vectors.",
    "The Eiffel Tower is in Paris.",
    "Async code does not block the event loop.",
]
_CORPUS_VECS = np.stack([mock_embed(t) for t in CORPUS])


@app.get("/nearest")
def nearest(q: str, k: int = 3) -> list[dict]:
    qv = mock_embed(q)
    scores = _CORPUS_VECS @ qv  # cosine sim because all normalised
    idx = np.argsort(-scores)[:k]
    return [{"text": CORPUS[i], "score": float(scores[i])} for i in idx]
