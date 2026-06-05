# 08 — File Uploads

Uploads are one of the most attacked, most memory-sensitive endpoints
in any service. Get them right.

## What we do (and why)

| Pattern                                     | Why it matters                                 |
|---------------------------------------------|------------------------------------------------|
| **Stream** the file in 1 MiB chunks         | Constant memory, no matter the file size       |
| Enforce **size limit while reading**        | A naive `file.read()` lets attackers OOM you   |
| Validate **content-type**                   | Cheap first filter                             |
| Validate **magic bytes**                    | Clients lie; the file does not                 |
| Use **safe filename**                       | Prevents `../etc/passwd` and weird shell chars |
| Use **per-upload UUID directory**           | Avoids collisions, isolates failed cleanups    |
| Use **aiofiles** for non-blocking disk IO   | Keeps the event loop responsive                |

## Run

```bash
uvicorn 08_file_uploads.app:app --reload --port 8000

# Upload a PDF (replace path)
curl -F "file=@./sample.pdf" http://localhost:8000/upload

# Upload too big — gets 413
dd if=/dev/zero of=/tmp/huge.bin bs=1M count=30
curl -F "file=@/tmp/huge.bin;type=application/pdf" http://localhost:8000/upload

# Fake PDF — gets 400 (magic bytes wrong)
echo "not a pdf" > /tmp/fake.pdf
curl -F "file=@/tmp/fake.pdf;type=application/pdf" http://localhost:8000/upload
```

## Why streaming?

A common mistake:

```python
data = await file.read()   # Loads everything into RAM. Don't.
size = len(data)
```

That works for 1 MB. It crashes for 2 GB. Always stream.

## Production checklist

- [ ] Per-route size limits (don't rely on a global only).
- [ ] Content-type allow-list, not deny-list.
- [ ] Magic-bytes check for binary formats (`%PDF-`, `PK\x03\x04`, etc).
- [ ] Filename sanitisation (`os.path.basename` + regex allow-list).
- [ ] Random per-upload directory; never trust client filename for the path.
- [ ] Scan with antivirus / `clamav` if accepting untrusted users.
- [ ] Store on object storage (S3) in real deployments — not local disk.
- [ ] Generate **download URLs that expire** (pre-signed) instead of
      serving from disk.
- [ ] Strip metadata from images/PDFs if you re-share them.

## CPU vs IO bound

A naive PDF parser is CPU-bound — it should NOT run inside the
async handler. Pattern:

```
async handler  ─▶  enqueue job  ─▶  worker process  ─▶  parse + summarise
```

We will build this end-to-end in chapters 21 and 29.

## Exercises

1. Accept multiple files in one request (`list[UploadFile]`). Apply the
   same size budget across all of them.
2. Add a checksum (`hashlib.sha256`) computed while streaming and
   return it in the response. Use it to deduplicate.
3. Switch the storage backend to **S3 multipart upload** (boto3). Keep
   the route the same.
