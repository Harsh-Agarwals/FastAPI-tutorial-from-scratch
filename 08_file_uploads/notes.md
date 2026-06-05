# Notes — Chapter 08

## Why `UploadFile` and not `bytes`?

`UploadFile` is a thin wrapper around a `SpooledTemporaryFile`. For
small files, it stays in memory; for big ones, it spills to disk.
You get an async `.read(size)` and `.seek()`.

## When does Starlette buffer to disk?

Default threshold: 1 MiB. Above that, requests get spooled to a temp
file. This means uploads do not arbitrarily blow up memory — but the
disk fills if you don't enforce limits.

## `python-multipart`

The library that parses `multipart/form-data`. We listed it in the
global `requirements.txt`. Without it, FastAPI raises an error the
moment you try to define a `File(...)` parameter.

## Performance tips

- Bigger chunks (1–4 MiB) reduce syscall overhead at the cost of
  responsiveness for cancellations.
- Disk write speed matters; tune your storage tier in cloud (gp3/io2
  on AWS) for upload-heavy workloads.
- Object storage (S3, GCS) lets clients upload directly via signed
  URLs — your API never sees the bytes. Best pattern at scale.
