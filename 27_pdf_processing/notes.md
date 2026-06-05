# Notes — Chapter 27

## Chunking is the most underrated part of RAG

If your retrieval feels bad, the fix is usually chunking, not the
model. Things to try:

- Slightly smaller chunks with more overlap
- Boundaries on headings / paragraphs / sentences (in that order)
- Add a *contextual header* (doc title + section) to each chunk before
  embedding

## CPU cost

Parsing a 100-page PDF is ~1-3 seconds of CPU. Do it in a process pool
to keep the event loop free (chapter 13).

## Memory

`PdfReader` loads the whole file into memory. For very large PDFs,
stream pages or convert to per-page PDFs first.

## Encrypted PDFs

Set `reader.decrypt(password)` before extraction. We don't expose this
in the route; doing so safely needs careful UX.
