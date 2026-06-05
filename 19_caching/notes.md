# Notes — Chapter 19

## Hit ratio is the only metric that matters

A cache that's never hit is just memory pressure. Instrument hits vs
misses and watch them post-launch. < 30% hit ratio? Reconsider the key
or scope.

## Time-to-live tuning

Start with TTL = max(acceptable_staleness, p95_request_period). For
LLM answers, hours-to-days is usually fine. For market data, seconds.

## Compression

For Redis storing big AI responses, consider compressing payloads
(`zstd` is fast). 5-10× shrink is common.

## Negative caching

Cache *misses* (404, "no result") for shorter durations to absorb hot
not-found queries.

## Don't cache PII without consent

Cached entries persist. Hashing the key is not enough — the *value*
may contain PII. Encrypt at rest or just don't cache.
