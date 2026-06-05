"""
Chapter 05 — Authentication

We build three increasingly real flows, side by side, so you can compare:

1. **API key in a header** (simplest; great for server-to-server)
2. **OAuth2 password flow** with JWT (typical SPA / mobile client)
3. **bcrypt password hashing** (never store plaintext passwords)

Disclaimer: this is *educational*. In production:
    - rotate JWT secrets
    - use refresh tokens
    - store users in a real DB
    - support OAuth2 providers (Google, GitHub) — out of scope here

Run:
    uvicorn 05_authentication.app:app --reload --port 8000

Try it at /docs — the "Authorize" button works with the password flow.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ---------- Config (in real life, load from env / Vault) ----------
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-do-not-use-in-prod")
JWT_ALG = os.getenv("JWT_ALG", "HS256")
JWT_EXP_MINUTES = int(os.getenv("JWT_EXP_MINUTES", "60"))
API_KEY = os.getenv("API_KEY", "local-dev-api-key")

app = FastAPI(title="Chapter 05 — Authentication")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


# --------------------------------------------------------------------------
# Fake user "DB". Note: only the HASH is stored, never the password.
# --------------------------------------------------------------------------
class UserInDB(BaseModel):
    username: str
    full_name: str
    hashed_password: str
    scopes: list[str] = []


_USERS: dict[str, UserInDB] = {
    "ada": UserInDB(
        username="ada",
        full_name="Ada Lovelace",
        hashed_password=pwd_ctx.hash("password123"),
        scopes=["read", "write"],
    ),
    "guest": UserInDB(
        username="guest",
        full_name="Guest User",
        hashed_password=pwd_ctx.hash("guest"),
        scopes=["read"],
    ),
}


class PublicUser(BaseModel):
    """What we return — no hash, no scopes leaking unless we want them."""

    username: str
    full_name: str
    scopes: list[str]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# --------------------------------------------------------------------------
# (1) API key flow — header-based, for service-to-service.
# --------------------------------------------------------------------------
def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str:
    if x_api_key != API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return x_api_key


@app.get("/ping/service")
def service_ping(_: Annotated[str, Depends(require_api_key)]) -> dict[str, str]:
    return {"msg": "ok — server-to-server"}


# --------------------------------------------------------------------------
# (2) OAuth2 password flow + JWT
# --------------------------------------------------------------------------
def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def _authenticate(username: str, password: str) -> UserInDB | None:
    user = _USERS.get(username)
    if not user or not _verify_password(password, user.hashed_password):
        return None
    return user


def _create_access_token(sub: str, scopes: list[str]) -> tuple[str, int]:
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES)
    payload = {"sub": sub, "scopes": scopes, "exp": expires}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG), JWT_EXP_MINUTES * 60


@app.post("/token", response_model=Token, tags=["auth"])
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """
    OAuth2 password flow. Swagger's "Authorize" button posts here.

    Production note: the password flow is being deprecated by OAuth2.1.
    Use it only for first-party clients you own (your own SPA / mobile app).
    """
    user = _authenticate(form.username, form.password)
    if not user:
        # Identical message for missing user / wrong pass: avoid user enumeration.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, exp = _create_access_token(user.username, user.scopes)
    return Token(access_token=token, expires_in=exp)


def current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserInDB:
    """Decode the JWT and load the user. Raises 401 on any failure."""
    creds_err = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        username = payload.get("sub")
        if not username:
            raise creds_err
    except JWTError:
        raise creds_err

    user = _USERS.get(username)
    if not user:
        raise creds_err
    return user


CurrentUser = Annotated[UserInDB, Depends(current_user)]


def require_scope(required: str):
    """Factory: build a dep that checks the user has a given scope."""

    def _checker(user: CurrentUser) -> UserInDB:
        if required not in user.scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing scope: {required}")
        return user

    return _checker


@app.get("/me", response_model=PublicUser, tags=["user"])
def me(user: CurrentUser) -> PublicUser:
    return PublicUser(**user.model_dump())


@app.get("/admin/write", tags=["user"])
def write_endpoint(user: Annotated[UserInDB, Depends(require_scope("write"))]) -> dict:
    return {"ok": True, "by": user.username}
