# 20 — Redis intro (the parts we need)

Redis is your **shared memory across processes**. We use it for:

- caches (chapter 19)
- rate limiting (chapter 18)
- queues (chapter 21)
- pub/sub broadcasts (chapter 16 at scale)
- session-ish data
- vector search prototyping (chapter 26)

## Start a Redis

```bash
docker run -d --name redis -p 6379:6379 redis:7
redis-cli ping     # PONG
```

## Run the app

```bash
uvicorn 20_redis_intro.app:app --reload --port 8000

# strings + TTL
curl -X POST 'http://localhost:8000/string/foo?value=bar&ttl=5'
curl http://localhost:8000/string/foo    # exists for 5 seconds

# counters
curl -X POST http://localhost:8000/counter/page-views
curl -X POST http://localhost:8000/counter/page-views

# hashes
curl -X POST http://localhost:8000/hash/user:42 \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada","plan":"pro"}'
curl http://localhost:8000/hash/user:42

# sorted set leaderboard
for u in alice bob carol; do
  curl -s -X POST "http://localhost:8000/zadd/leaderboard?member=$u&score=$((RANDOM%100))" > /dev/null
done
curl http://localhost:8000/ztop/leaderboard
```

## Data-type cheat sheet

| Type        | Use case                          | Notable commands             |
|-------------|-----------------------------------|------------------------------|
| String      | cache / counter                   | GET SET INCR EXPIRE          |
| Hash        | small "record"                    | HSET HGETALL HDEL            |
| List        | FIFO/LIFO queue                   | LPUSH RPUSH LPOP BLPOP       |
| Set         | uniqueness                        | SADD SISMEMBER SREM SCARD    |
| Sorted set  | ranked / time-windowed            | ZADD ZRANGE ZRANGEBYSCORE    |
| Stream      | append-only log (Kafka-lite)      | XADD XREAD XREADGROUP        |
| Pub/Sub     | fire-and-forget broadcast         | PUBLISH SUBSCRIBE            |

## Two production rules

1. **Always set a TTL** when caching. Otherwise your DB *is* Redis.
2. **Use pipelines / Lua** for multi-step atomic operations. A round
   trip per command kills throughput.

## Pub/Sub demo

In one terminal:
```bash
curl http://localhost:8000/subscribe-once/news
```
In another:
```bash
curl -X POST 'http://localhost:8000/publish/news?message=hi'
```
The first one returns immediately with the message.

## Exercises

1. Build a small "presence" service: `SADD online:room1 user-42` on
   connect, `SREM` on disconnect, `SMEMBERS` for the list.
2. Implement a deduper for events: `SADD dedupe <event_id>` and skip
   if already there. TTL the set.
3. Use a sorted set as a delayed-job queue: score = run_at_timestamp.
   A worker polls with `ZRANGEBYSCORE 0 now`.
