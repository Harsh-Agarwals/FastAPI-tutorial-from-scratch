# Notes — Chapter 06

## Middleware vs dep

| Question                                | Answer                       |
|-----------------------------------------|------------------------------|
| Does it apply to *every* route?         | Middleware                   |
| Does it apply only to specific routes?  | Dependency                   |
| Does it need to mutate the response?    | Middleware                   |
| Does it need a clean test seam?         | Dependency (overridable)     |

## Don't put heavy IO in `dispatch`

It runs for *every* request. A Redis hit per request is fine; an LLM
call per request will melt your service.

## CSP (Content Security Policy)

Not added by default — every app needs its own. A reasonable starter
for an API (no HTML): `Content-Security-Policy: default-src 'none'`.

## Logging best practices

- Use structured logs (key=value or JSON). Easier to parse in
  Loki / Datadog / CloudWatch.
- Always include a request id. It is the single most useful field
  in production debugging.
