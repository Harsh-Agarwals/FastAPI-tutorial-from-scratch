# 05 — Authentication

Three flows. Pick the right one for your use case.

| Flow              | Use when                                       | Where the secret goes      |
|-------------------|------------------------------------------------|----------------------------|
| **API key**       | Server-to-server, internal jobs, CLIs          | `X-API-Key` header         |
| **JWT (Bearer)**  | Browser / mobile app talking to your backend   | `Authorization: Bearer X`  |
| **Session cookie**| Server-rendered apps (not covered here)        | `Set-Cookie`               |

## Run

```bash
uvicorn 05_authentication.app:app --reload --port 8000
```

Open <http://localhost:8000/docs>. Click **Authorize** → username `ada`,
password `password123`. Try `/me` — works. `/admin/write` works because
`ada` has the `write` scope. Logout, login as `guest` (password `guest`)
and watch `/admin/write` return **403**.

## API key example

```bash
curl -i http://localhost:8000/ping/service        # 401
curl -i -H "X-API-Key: local-dev-api-key" http://localhost:8000/ping/service
```

## JWT example end-to-end

```bash
# 1. Get a token
TOKEN=$(curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ada&password=password123" | jq -r .access_token)

# 2. Call a protected endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/me

# 3. Scope failure
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/write
# ada has write → 200. Try the same with guest → 403.
```

## What's happening under the hood

1. `OAuth2PasswordBearer(tokenUrl="/token")` does *two* things:
   - Tells Swagger UI to show an Authorize button.
   - Becomes a dep that extracts the `Authorization: Bearer <token>` header.
2. `/token` validates credentials, signs a JWT (`HS256` here).
3. The JWT carries `sub` (subject = username), `scopes`, and `exp`.
4. `current_user` decodes the JWT on every request, raising 401 on any failure.

## Why hash with bcrypt?

- bcrypt has a **work factor** — you can tune the cost as CPUs get faster.
- It includes a per-password **salt** automatically — rainbow tables don't work.
- It is constant time, resistant to timing attacks.

`passlib`'s `CryptContext` lets you migrate algorithms over time
(e.g. bcrypt → argon2) without a flag day.

## Common mistakes (read this twice)

- **Storing JWT in `localStorage`** opens XSS-stealing risks. Prefer
  `HttpOnly` cookies for browser clients.
- **Long-lived JWTs.** Treat access tokens like cash: short TTL +
  refresh tokens.
- **Different error messages for "no such user" vs "bad password".**
  Lets attackers enumerate users. Use one generic message.
- **JWT as a session store.** JWTs can't be revoked easily. If you need
  revocation, keep a deny-list of `jti` (JWT id) in Redis.
- **Putting secrets in the JWT payload.** It is base64 — not encrypted.

## Exercises

1. Add refresh tokens: `/token/refresh` issues a new access token if
   the refresh token is valid. Store refresh tokens in memory + a deny-list.
2. Replace the in-memory `_USERS` with an async SQLAlchemy session (after
   chapter 22).
3. Swap HS256 (shared secret) for RS256 (public/private keypair). What
   changes for the consumer side?
4. Add a `last_login_at` timestamp updated inside `current_user`.
