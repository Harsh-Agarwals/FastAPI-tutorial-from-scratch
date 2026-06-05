# 25 — Embeddings (intuition first)

An embedding is **a function `text -> vector`** with one property:
semantically similar texts produce vectors that are close to each
other (by cosine or Euclidean distance).

That's it. The "AI magic" we then build on top of embeddings:
- semantic search
- retrieval-augmented generation (RAG)
- clustering / deduplication
- recommendations

## The toy embedder

We use a **deterministic 16-dimensional embedder** built from
character bucket counts. Real embedders (OpenAI's `text-embedding-3-small`)
produce 1536-d vectors trained on enormous corpora. The *interfaces*
are identical:

```
text  ──▶  embed()  ──▶  np.array[N]   (then L2-normalised)
```

By using a toy embedder, you can **debug the math** without API keys.

## Run

```bash
uvicorn 25_embeddings_intro.app:app --reload --port 8000

curl -X POST http://localhost:8000/embed \
  -H 'Content-Type: application/json' \
  -d '{"texts":["hello world","goodbye sun"]}'

curl -X POST http://localhost:8000/similarity \
  -H 'Content-Type: application/json' \
  -d '{"a":"cats are cute","b":"kittens are adorable"}'

curl 'http://localhost:8000/nearest?q=event+loop&k=3'
```

## Distance: cosine vs Euclidean

- **Cosine similarity** = `dot(a, b)` after L2-normalisation. Range
  `[-1, 1]`. The default for text embeddings.
- **Euclidean (L2)** distance also works; on normalised vectors the
  two are monotonic.

```
cosine(a,b) = 1   →  identical direction (similar)
cosine(a,b) = 0   →  orthogonal (unrelated)
cosine(a,b) = -1  →  opposite (rare for embeddings)
```

## Production embedder

Swap `mock_embed` for OpenAI:

```python
from openai import AsyncOpenAI
client = AsyncOpenAI()
r = await client.embeddings.create(model="text-embedding-3-small", input=texts)
vecs = [np.array(d.embedding, dtype=np.float32) for d in r.data]
```

Batch inputs — `text-embedding-3-small` accepts arrays. Always
normalise: many vector DBs expect that.

## Exercises

1. Find a *false positive* in the toy embedder — two texts the
   embedder thinks are similar but a human disagrees with. Why?
2. Increase the dimension by adding more buckets. Does the result
   improve? Why is there a limit?
3. Swap in the real embedder behind the same `embed()` API. The rest
   of the code shouldn't change. Mission accomplished.
