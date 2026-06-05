# Notes — Chapter 30

## Vertical scaling has a ceiling

Bigger CPUs help up to a point. After that, your code path is the
bottleneck. Profile before scaling up.

## Sticky sessions are an anti-pattern

If a client must hit the same instance to work, you have state. Move
it out (Redis, DB). Rolling deploys become painless.

## Circuit breakers

If an upstream is failing 50% of calls, *stop calling it* for a while.
Reduces cascading failure. Libraries: `pybreaker`, `aiobreaker`.

## Graceful shutdown

Listen for SIGTERM, stop accepting new requests, drain in-flight ones,
finish background jobs you can in N seconds. Otherwise deploys cause
visible errors.

## Multi-region

Eventually you need data near users. Postgres logical replication +
Redis cross-region replicas + CDN. Expensive but real for global apps.
