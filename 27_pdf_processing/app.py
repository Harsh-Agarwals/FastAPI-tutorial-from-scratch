"""
Chapter 27 — PDF processing fundamentals.

We do four things you'll need in any AI-on-documents system:

1. Extract text per-page from a PDF (pypdf).
2. Normalise whitespace.
3. Chunk into ~N-token blocks with overlap.
4. (Optional) Lightweight metadata: page numbers, character offsets.

Note: pypdf cannot do OCR. If you need text from scanned PDFs, pipe
the bytes through Tesseract / Ocrmypdf first.

Run:
    uvicorn 27_pdf_processing.app:app --reload --port 8000
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader

app = FastAPI(title="Chapter 27 — PDF Processing")


# ---------------------------------------------------------------------------
# Pure functions — easy to test, no HTTP coupling.
# ---------------------------------------------------------------------------
def extract_pages(pdf_bytes: bytes) -> list[str]:
    import io
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [(p.extract_text() or "") for p in reader.pages]


_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Collapse weird whitespace and strip control characters."""
    text = text.replace("\u00ad", "")            # soft hyphens
    text = _WS.sub(" ", text)                    # any whitespace -> single space
    return text.strip()


@dataclass
class Chunk:
    page_start: int
    page_end: int
    text: str
    char_start: int
    char_end: int


def chunk_text(
    pages: list[str],
    target_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[Chunk]:
    """
    Produce overlapping chunks of approximately `target_chars` characters.
    Overlap helps LLMs retain context across boundaries.
    """
    chunks: list[Chunk] = []
    # Build a flat string and remember the page boundaries.
    flat: list[str] = []
    page_offsets: list[int] = []  # char index where each page starts in `flat`

    for i, p in enumerate(pages):
        normalised = normalise(p)
        if not normalised:
            continue
        page_offsets.append(sum(len(s) + 1 for s in flat))
        flat.append(normalised)
    full = "\n".join(flat)

    def page_of(char_idx: int) -> int:
        # Find the largest page whose offset <= char_idx.
        page = 0
        for i, off in enumerate(page_offsets):
            if off <= char_idx:
                page = i
            else:
                break
        return page

    start = 0
    while start < len(full):
        end = min(start + target_chars, len(full))
        # Try to break at the nearest sentence end for cleaner chunks.
        if end < len(full):
            window = full[start:end]
            last_dot = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
            if last_dot > target_chars // 2:
                end = start + last_dot + 1
        text = full[start:end].strip()
        if text:
            chunks.append(Chunk(
                page_start=page_of(start),
                page_end=page_of(max(start, end - 1)),
                text=text,
                char_start=start,
                char_end=end,
            ))
        if end == len(full):
            break
        start = max(end - overlap_chars, end)  # advance with overlap
    return chunks


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
class ChunkOut(BaseModel):
    page_start: int
    page_end: int
    text: str
    char_start: int
    char_end: int


class PDFOut(BaseModel):
    pages: int
    total_chars: int
    chunks: list[ChunkOut]


@app.post("/parse", response_model=PDFOut)
async def parse(file: UploadFile = File(...)) -> PDFOut:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(415, "Only application/pdf is accepted")
    data = await file.read()
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "Not a PDF (missing %PDF- header)")
    try:
        pages = extract_pages(data)
    except Exception as e:
        raise HTTPException(422, f"Could not parse PDF: {e}")
    chunks = chunk_text(pages)
    return PDFOut(
        pages=len(pages),
        total_chars=sum(len(p) for p in pages),
        chunks=[ChunkOut(**c.__dict__) for c in chunks],
    )
