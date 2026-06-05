# Notes — Chapter 26

## Brute force vs ANN

For N≤100k vectors of d≤1536 floats, brute force with numpy is fine
and *exact*. ANN sacrifices recall for speed; tune `efSearch` /
`nprobe` to find the right balance.

## Dimensionality reduction

You can shrink 1536-d embeddings with PCA before indexing — sometimes
recall drops marginally and storage/cost plummet.

## Re-ranking

Vector search retrieves likely candidates; a cross-encoder reranker
scores them more precisely. Reranking the top 20 with a heavier model
usually improves quality more than tuning the index.

## RAG in one sentence

Retrieval-Augmented Generation = (vector search top K) → stuff into
prompt → LLM → answer. The "magic" is in chunking, retrieval quality,
and prompt design — not in the LLM call itself.
