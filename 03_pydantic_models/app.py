"""
Chapter 03 — Pydantic Models, the right way.

Pydantic v2 is the validation engine FastAPI relies on. Mastering it
means cleaner code and fewer bugs at the API boundary.

We cover:
- field constraints (Field, conint, etc.)
- custom validators (`field_validator`, `model_validator`)
- model composition (nested models, lists of models)
- response shaping (separate Create / Read / Update models)
- aliases (camelCase outside, snake_case inside)
- computed fields
- discriminated unions (tagged variants)

Run:
    uvicorn 03_pydantic_models.app:app --reload --port 8000
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

app = FastAPI(title="Chapter 03 — Pydantic Models")


# --------------------------------------------------------------------------
# 1. Field constraints + aliases
# --------------------------------------------------------------------------
class UserCreate(BaseModel):
    """
    What clients send to create a user.

    `model_config` opts in to:
      - populate_by_name: accept BOTH camelCase (alias) and snake_case (name).
      - str_strip_whitespace: trim incoming strings automatically.
    """

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=80, alias="fullName")
    age: Annotated[int, Field(ge=13, le=130)]
    password: str = Field(min_length=8, exclude=True)  # exclude from serialization

    @field_validator("password")
    @classmethod
    def password_must_have_digit(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("password must contain at least one digit")
        return v


class UserRead(BaseModel):
    """
    What we send BACK. Notice `password` is gone, and we serialize
    field names in camelCase for JS-friendly clients via `by_alias`.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int
    email: EmailStr
    full_name: str = Field(alias="fullName")
    age: int
    created_at: datetime = Field(alias="createdAt")

    @computed_field  # type: ignore[misc]
    @property
    def is_adult(self) -> bool:
        return self.age >= 18


# --------------------------------------------------------------------------
# 2. Model-level validation (cross-field rules)
# --------------------------------------------------------------------------
class DateRange(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _end_after_start(self) -> "DateRange":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


# --------------------------------------------------------------------------
# 3. Discriminated unions (tagged variants)
# Cleanly model "this can be one of N shapes, picked by a field".
# Great for webhooks, events, polymorphic payloads.
# --------------------------------------------------------------------------
class CardPayment(BaseModel):
    kind: Literal["card"] = "card"
    last4: str = Field(min_length=4, max_length=4)


class BankPayment(BaseModel):
    kind: Literal["bank"] = "bank"
    iban: str


PaymentMethod = Annotated[CardPayment | BankPayment, Field(discriminator="kind")]


class Order(BaseModel):
    amount_cents: int = Field(gt=0)
    payment: PaymentMethod


# --------------------------------------------------------------------------
# Fake "DB"
# --------------------------------------------------------------------------
_USERS: dict[int, UserRead] = {}
_NEXT_ID = 1


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.post("/users", response_model=UserRead, response_model_by_alias=True)
def create_user(payload: UserCreate) -> UserRead:
    global _NEXT_ID
    user = UserRead(
        id=_NEXT_ID,
        email=payload.email,
        full_name=payload.full_name,
        age=payload.age,
        created_at=datetime.now(timezone.utc),
    )
    _USERS[_NEXT_ID] = user
    _NEXT_ID += 1
    return user


@app.get("/users/{user_id}", response_model=UserRead, response_model_by_alias=True)
def get_user(user_id: int) -> UserRead:
    if user_id not in _USERS:
        raise HTTPException(404, "User not found")
    return _USERS[user_id]


@app.post("/date-range")
def check_range(r: DateRange) -> dict[str, str]:
    return {"ok": "range is valid", "duration_s": str((r.end - r.start).total_seconds())}


@app.post("/orders")
def place_order(order: Order) -> dict:
    # Thanks to the discriminator, `order.payment` is correctly typed.
    return {"received": order.model_dump()}
