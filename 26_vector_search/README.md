# 26 — Vector Search

We build a **tiny in-memory vector index** (numpy + a list) so the
operations are obvious. The route shapes match what you would build
on top of FAISS / pgvector / Pinecone.

## Run

```bash
uvicorn 26_vector_search.app:app --reload --port 8000

# Upsert
curl -X POST http://localhost:8000/index/items \
  -H 'Content-Type: application/json' \
  -d '{"items":[
    {"text":"FastAPI is great for APIs.", "tags":["python","web"]},
    {"text":"Async code does not block.", "tags":["python","async"]},
    {"text":"Pasta with tomato sauce.", "tags":["food"]}
  ]}'

# Search
curl 'http://localhost:8000/search?q=event+loop&k=2'

# Filter + search
curl 'http://localhost:8000/search-filter?q=python&tag=web'
```

## What an ANN library buys you

Our index is exact (brute force): `O(N*d)` per query. Fine up to a few
hundred thousand vectors. Beyond that you want **approximate nearest
neighbour** (ANN):

| Library / Service | Index             | Notes                            |
|-------------------|-------------------|----------------------------------|
| FAISS             | HNSW, IVF, PQ     | C++ with Python bindings         |
| pgvector          | IVFFLAT, HNSW     | Postgres extension. Great default. |
| Pinecone          | managed           | Serverless, multi-tenant         |
| Weaviate          | HNSW              | Self-host, GraphQL               |
| Redis Stack       | HNSW              | If you already use Redis         |

Switching means: replace `_index.add` and `_index.search` with library
calls. The FastAPI handlers stay identical.

## Hybrid search

Pure vector search misses exact-keyword cases. Real systems combine:

1. Vector top-K (semantic)
2. Lexical top-K (BM25 / Elasticsearch)
3. Reranker (cross-encoder) over the union

We will not build that here, but it's worth knowing.

## Production checklist

- [ ] Persistent storage (not in-memory).
- [ ] Async-safe writes — usually batched offline.
- [ ] Metadata filters (`tag in [...]`, `created_after`).
- [ ] Per-tenant namespaces.
- [ ] Index rebuilds when embedder version bumps.
- [ ] Re-rank top-K with a heavier model if quality matters.

## Exercises

1. Add an `update` and `delete` to the index. Watch how
   "tombstones + rebuild" becomes a real concern at scale.
2. Replace `_index` with FAISS HNSW. Confirm route shapes don't change.
3. Add a `created_after` filter; explore how that interacts with the
   ANN structures.
