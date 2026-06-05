# 27 — PDF Processing

Most "AI on documents" pipelines have the same shape:

```
PDF ─▶ extract text per page ─▶ normalise ─▶ chunk ─▶ embed / summarize
```

We build the first three stages here. Chunking is the lever that
controls quality and cost downstream.

## Run

```bash
uvicorn 27_pdf_processing.app:app --reload --port 8000

# Upload a real PDF
curl -F "file=@/path/to/sample.pdf;type=application/pdf" http://localhost:8000/parse | jq '.pages, .chunks | length'
```

## Why chunk?

1. LLM context windows are bounded (4k–200k tokens).
2. Smaller chunks → cheaper to summarise each one.
3. Overlap (~10-15%) preserves context across boundaries.
4. Each chunk gets its own embedding for retrieval.

Typical defaults:

- **target_chars** 800–1500 (about 200–400 tokens).
- **overlap_chars** 100–200.
- Break at sentence boundaries when possible.

## When `pypdf` is not enough

- **Scanned PDFs** (image PDFs): `pypdf` returns empty strings. Use
  `ocrmypdf` or call Tesseract to add a text layer first.
- **Tables / multi-column** layouts: `pypdf` flattens them. Use
  `unstructured`, `pdfplumber`, or layout-aware models.
- **Math / equations**: usually lost. Pre-extract as LaTeX if you can.

## Production tips

- **Process in worker processes**, not the request handler — parsing is CPU.
- **Limit page count** in your handler (`MAX_PAGES`) and reject early.
- **Hash the file** and cache the parsed chunks — re-parsing is wasteful.
- **Store chunks**, not full PDFs, in your vector index.

## Exercises

1. Add per-chunk approximate **token** counts (`len(text.split()) * 0.75`
   or `tiktoken`).
2. Try chunking by **headings** (split on lines matching `^\s*\d+(\.\d+)*\s`).
3. Use multiprocessing (`ProcessPoolExecutor`) to parse 50 PDFs in
   parallel and compare to sequential.
