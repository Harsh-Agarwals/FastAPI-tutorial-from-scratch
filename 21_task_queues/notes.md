# Notes — Chapter 21

## At-least-once vs exactly-once

Almost every queue is **at-least-once**. Your worker must be
idempotent: if the same job runs twice, the result is the same.

Practical: use the job id as a dedupe key in your output storage.

## Visibility timeout

Redis lists don't have one by default. If a worker dies between
BLPOP and finishing, the job is lost. Improvements:
- use Redis **Streams** with consumer groups (built-in ack + claim)
- use Celery with `acks_late=True`
- use a real broker (RabbitMQ, SQS) with visibility timeout

## Backpressure

Producers (your API) can ingest faster than workers can process. Watch
queue depth; if it grows, either add workers or 503 new requests.

## Health checks

A worker that hasn't completed a job in N minutes might be stuck.
Heartbeat to Redis (`SET worker:<id>:hb now`, TTL=60s); kill if stale.

## What Celery / RQ buy you

- Schedules and cron
- Task chains (A → B → C)
- Result backends
- Worker autoscaling with prefork / gevent
- A management UI (Flower)
- The hard-won correctness from years of production
