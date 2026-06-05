# Notes — Chapter 25

## Why normalise?

Cosine similarity collapses to a dot product on L2-normalised vectors.
Faster, simpler math, and most ANN indexes (HNSW, IVF) assume it.

## Embedding dimensionality

| Model                        | Dim   |
|------------------------------|------:|
| text-embedding-3-small       | 1536  |
| text-embedding-3-large       | 3072  |
| OSS small sentence-transformers | 384   |

Bigger isn't always better — disk + RAM cost scales linearly, ANN
recall is often comparable above ~500-d.

## Token limits

Each embedder caps input length (e.g. 8k tokens). Chunk longer text
(chapter 27).

## Cost shape

Embeddings are cheap. The cost is **storage and search** at scale, not
the model call. Cache aggressively.
