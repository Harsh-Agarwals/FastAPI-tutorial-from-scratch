# Notes — Chapter 29 (Capstone)

## What makes this "production-shaped"

- API has *no* mutable state. Restart any time.
- Long work happens elsewhere. The API is a thin coordinator.
- Communication is over Redis — many languages can join the system.
- Progress is observable in three ways: status hash, pub/sub stream,
  worker logs.

## Hot spots to monitor

- queue depth (`LLEN queue:summarize_pdf`)
- worker p95 job time
- cache hit ratio
- LLM token spend per day

## Deploy sketch

```
api   → 3 uvicorn workers behind nginx
worker → 4 worker pods (k8s deployment)
redis → managed (Elasticache/MemoryDB)
storage → S3 (replace local _uploads/)
```

## Failure modes to verify

- Redis flaps → API responds 503, workers crash-loop until back.
- LLM down → retries fire; queue grows; alarms fire.
- One PDF is malformed → only that job fails; queue keeps moving.
- Worker dies mid-job → BLPOP has already removed item; the job is
  lost. Mitigation: switch to Redis Streams with consumer groups, or
  add a "claimed" zset with TTL to detect and requeue.

## A small joke worth remembering

Every system you build that isn't trivially small *will* eventually
need: queues, retries, idempotency, caching, observability. Better to
add them when you can choose to than when production is on fire.
