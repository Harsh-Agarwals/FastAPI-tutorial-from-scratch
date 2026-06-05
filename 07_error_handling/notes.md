# Notes — Chapter 07

## Why a domain-error layer?

It separates **what went wrong** (a business concept) from **how we
tell the client** (an HTTP status). The boundary maps one to the
other; the business code stays HTTP-free and testable.

## Logging strategy

- Domain errors → `log.warning` (expected)
- Validation errors → `log.info` (very common)
- HTTPException 5xx → `log.error`
- Unhandled `Exception` → `log.exception` (full traceback)

This keeps your dashboards meaningful.

## Useful media type

`application/problem+json` (RFC 7807) is recognized by some tooling
and makes the intent obvious. Stick to it.

## Don't render exceptions in production

A traceback contains code paths, library versions, sometimes secrets.
Never put it in a response body. Use a request id to tie the user-
facing 500 to your server-side logs.
