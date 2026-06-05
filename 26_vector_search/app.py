"""
Chapter 26 — Vector search (a tiny in-memory index).

Goal: build intuition for what Pinecone / Weaviate / pgvector / FAISS
all do under the hood. We support:

- /index/items                      upsert documents (text → embedding)
- /search?q=...&k=5                 nearest neighbour by cosine sim
- /search-filter?tag=...            attribute filter + nearest neighbour

For real production, replace `_index` with FAISS / pgvector / Pinecone.
The route shapes do not change.

Run:
    uvicorn 26_vector_search.app:app --reload --port 8000
"""
from __future__ import annotations

import threading
import uuid
from typing import Annotated

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Re-use the toy embedder from chapter 25. We can't say `import 25_embeddings_intro`
# (Python's parser rejects digit-prefix identifiers), but `importlib` is happy.
import sys, pathlib, importlib
_REPO_ROOT = str(pathlib.Path(__file__).parent.parent.resolve())
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
mock_embed = importlib.import_module("25_embeddings_intro.app").mock_embed

app = FastAPI(title="Chapter 26 — Vector Search")


# ---------------------------------------------------------------------------
# Tiny in-memory index. Thread-safe enough for the demo, not production.
# ---------------------------------------------------------------------------
class VectorIndex:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.ids: list[str] = []
        self.texts: list[str] = []
        self.tags: list[set[str]] = []
        self.vecs = np.zeros((0, dim), dtype=np.float32)
        self._lock = threading.Lock()

    def add(self, text: str, tags: list[str]) -> str:
        v = mock_embed(text).astype(np.float32)
        assert v.shape == (self.dim,)
        with self._lock:
            self.ids.append(uuid.uuid4().hex[:12])
            self.texts.append(text)
            self.tags.append(set(tags))
            self.vecs = np.vstack([self.vecs, v[None, :]])
            return self.ids[-1]

    def search(self, query: str, k: int = 5, must_have_tag: str | None = None):
        if len(self.ids) == 0:
            return []
        qv = mock_embed(query).astype(np.float32)
        with self._lock:
            scores = self.vecs @ qv          # cosine (vectors are normalised)
            order = np.argsort(-scores)
            results = []
            for i in order:
                if must_have_tag and must_have_tag not in self.tags[i]:
                    continue
                results.append({
                    "id": self.ids[i],
                    "text": self.texts[i],
                    "tags": sorted(self.tags[i]),
                    "score": float(scores[i]),
                })
                if len(results) == k:
                    break
            return results


_index = VectorIndex(dim=16)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
class Item(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    tags: list[str] = []


class BulkUpsert(BaseModel):
    items: list[Item]


@app.post("/index/items")
def upsert(payload: BulkUpsert) -> dict:
    ids = [_index.add(it.text, it.tags) for it in payload.items]
    return {"added": len(ids), "ids": ids}


@app.get("/search")
def search(q: Annotated[str, "query string"], k: int = 5) -> list[dict]:
    return _index.search(q, k)


@app.get("/search-filter")
def search_filter(q: str, tag: str, k: int = 5) -> list[dict]:
    return _index.search(q, k, must_have_tag=tag)


@app.get("/stats")
def stats() -> dict:
    return {"size": len(_index.ids), "dim": _index.dim}
