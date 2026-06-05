# 30 — Scalability concepts

This is mostly a reading chapter. Patterns more than code. The
accompanying `app.py` is a deliberately minimal stateless service to
demonstrate horizontal scale.

## The seven dimensions of scale

1. **Statelessness** — no instance is special. Anyone can answer any
   request. State lives in Redis / Postgres / object storage.
2. **Horizontal first** — add replicas, not bigger machines. Bigger
   machines have failure-blast-radius problems.
3. **Async + connection reuse** — fewer threads, more concurrency,
   pool connections to upstreams.
4. **Backpressure** — bounded queues, rate limits, timeouts. Never
   accept work you can't finish.
5. **Caching** — every cycle saved is a real win.
6. **Idempotency + retries** — at-least-once everywhere.
7. **Observability** — without it, you cannot scale safely.

## Common bottlenecks in AI backends

| Bottleneck         | Symptom                              | Fix                                |
|--------------------|--------------------------------------|------------------------------------|
| LLM rate limits    | 429s, queue growth                   | Semaphores, retry, multi-key       |
| Single Redis node  | latency spikes under load            | Cluster / managed Redis            |
| DB connections     | "too many connections"               | Pool sizing, pgbouncer             |
| Big PDFs           | event loop stalls                    | Process pool + queue               |
| Cold starts        | first request slow                   | Pre-warm container, share clients  |
| Logging IO         | high CPU at high RPS                 | Async / non-blocking log writers   |

## Run

```bash
docker run -d --name redis -p 6379:6379 redis:7
uvicorn 30_scalability_concepts.app:app --port 8000 --workers 4

# See requests being served by different worker PIDs
for i in {1..20}; do curl -s http://localhost:8000/who | jq -r .pid; done | sort | uniq -c
```

`/count` is monotonic across workers because the counter lives in
Redis. Open `redis-cli`, run `MONITOR`, and watch `INCR global:count`
fly past.

## Deployment shapes

- **Dev**: 1 uvicorn worker, sqlite, in-process Redis stub.
- **Small prod**: 1 box, N workers behind nginx, managed Redis +
  Postgres.
- **Production**: container orchestration (Kubernetes / ECS), HPA on
  CPU + queue depth, blue/green deploys, multiple AZs.

## Recommended reading

- *Designing Data-Intensive Applications* — Kleppmann
- *The Twelve-Factor App* — heroku.com
- *Site Reliability Engineering* — Google
- *Release It!* — Nygard (timeouts, bulkheads, circuit breakers)
