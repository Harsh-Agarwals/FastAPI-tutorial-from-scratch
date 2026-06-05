"""
Chapter 08 — File Uploads (with PDFs in mind)

We focus on the patterns that scale to real services:
  - Async streaming writes (don't read entire file into RAM)
  - Hard size limits (enforced *while reading*, not after)
  - Content-type + magic-bytes validation
  - Safe filenames + per-upload UUID directories
  - Temporary vs persistent storage

Run:
    uvicorn 08_file_uploads.app:app --reload --port 8000

Try uploading a small PDF or text file:
    curl -F "file=@/path/to/sample.pdf" http://localhost:8000/upload
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./_uploads")).resolve()
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
CHUNK = 1024 * 1024  # 1 MiB — sweet spot for disk + network

ALLOWED_CT = {
    "application/pdf",
    "text/plain",
    "application/octet-stream",  # some browsers send this for unknown files
}

# Magic numbers — first bytes of file types. Trust these over Content-Type.
MAGIC_PDF = b"%PDF-"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Chapter 08 — File Uploads")


class UploadResult(BaseModel):
    id: str
    filename: str
    size_bytes: int
    content_type: str | None
    path: str


def _safe_filename(name: str) -> str:
    """Strip directory components and dangerous characters."""
    base = os.path.basename(name or "file")
    # Replace anything weird with underscore.
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    # Avoid hidden / empty names.
    return base.lstrip(".") or "file"


@app.post("/upload", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload(file: Annotated[UploadFile, File(description="A small file (≤ MAX_UPLOAD_MB MB)")]) -> UploadResult:
    # 1. Cheap checks first: content type + filename.
    if file.content_type not in ALLOWED_CT:
        raise HTTPException(415, f"Unsupported content type: {file.content_type}")

    upload_id = uuid.uuid4().hex
    safe = _safe_filename(file.filename or "upload")
    target_dir = UPLOAD_DIR / upload_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe

    # 2. Stream the body to disk in chunks. We *never* load the whole file
    #    in memory — a 2 GiB upload would otherwise OOM the worker.
    total = 0
    first_chunk: bytes | None = None
    async with aiofiles.open(target, "wb") as out:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            if first_chunk is None:
                first_chunk = chunk[:8]
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                # Stop early; clean up partial file.
                await out.close()
                target.unlink(missing_ok=True)
                target_dir.rmdir()
                raise HTTPException(413, f"File too large; limit is {MAX_UPLOAD_MB} MB")
            await out.write(chunk)

    # 3. Magic-bytes check for PDFs (don't trust the client).
    if file.content_type == "application/pdf" and first_chunk and not first_chunk.startswith(MAGIC_PDF):
        target.unlink(missing_ok=True)
        target_dir.rmdir()
        raise HTTPException(400, "File claims to be PDF but is missing the %PDF- header")

    return UploadResult(
        id=upload_id,
        filename=safe,
        size_bytes=total,
        content_type=file.content_type,
        path=str(target),
    )


@app.get("/uploads")
def list_uploads() -> list[dict]:
    """Tiny helper to see what was stored — never exposed in real prod."""
    out: list[dict] = []
    for d in UPLOAD_DIR.iterdir():
        if not d.is_dir():
            continue
        for f in d.iterdir():
            out.append({"id": d.name, "name": f.name, "size": f.stat().st_size})
    return out
