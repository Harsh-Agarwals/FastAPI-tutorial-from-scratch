# Notes — Chapter 05

## JWT structure

A JWT is three base64url-encoded parts separated by dots:
`header.payload.signature`. Decode the middle part on
<https://jwt.io> — it is **not** encrypted, just signed.

## When to choose what

| Need                            | Pick                          |
|---------------------------------|-------------------------------|
| Internal cron job hitting API   | API key (header)              |
| Browser SPA, want CSRF safety   | Session cookie (HttpOnly)     |
| Mobile app, can store token     | JWT Bearer + refresh tokens   |
| Federated identity (Google etc) | OAuth2 Authorization Code +PKCE|

## Security checklist (production)

- [ ] HTTPS only — Bearer tokens leak in plain HTTP.
- [ ] Short access-token TTL (15 min) + refresh tokens (days).
- [ ] Rotate JWT signing secret periodically (key id `kid` in header).
- [ ] Rate-limit `/token` (chapter 18) — defends against brute force.
- [ ] Lock accounts after N failed logins.
- [ ] Audit log: who logged in, from where, when.
- [ ] CSRF protection if using cookies.
- [ ] Strong password rules + breached-password check (HIBP).

## Debugging

- `python -c "import jwt as j; ..."` — note: we use `python-jose`, not `pyjwt`.
- Use Swagger's Authorize dialog; if it says "Invalid", check `tokenUrl`.
- 401 vs 403: 401 means "I don't know who you are", 403 means
  "I know who you are, you can't do this".
