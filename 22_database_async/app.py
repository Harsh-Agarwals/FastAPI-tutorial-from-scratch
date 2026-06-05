"""
Chapter 22 — Async databases with SQLAlchemy 2.x.

We use `sqlite+aiosqlite` for portability (no setup). The same code
works against Postgres if you change the URL to `postgresql+asyncpg://...`.

Pattern shown:
- async engine + session
- yield-based DB dep
- declarative models
- a tiny repository layer (keep handlers slim)
- transactions

Run:
    uvicorn 22_database_async.app:app --reload --port 8000
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")


# --- ORM ---------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


# --- Engine + session factory (one per process) -----------------------------
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Chapter 22 — Async DB (SQLAlchemy 2.x)", lifespan=lifespan)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


DB = Annotated[AsyncSession, Depends(get_session)]


# --- Schemas -----------------------------------------------------------------
class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class NoteOut(NoteIn):
    id: int
    created_at: datetime


# --- Routes ------------------------------------------------------------------
@app.post("/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create(payload: NoteIn, db: DB) -> Note:
    note = Note(title=payload.title, body=payload.body)
    db.add(note)
    await db.flush()  # populate auto-increment id
    return note


@app.get("/notes", response_model=list[NoteOut])
async def list_notes(db: DB, limit: int = 20) -> list[Note]:
    result = await db.scalars(select(Note).order_by(Note.id.desc()).limit(limit))
    return list(result)


@app.get("/notes/{note_id}", response_model=NoteOut)
async def get_one(note_id: int, db: DB) -> Note:
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(404, "not found")
    return note


@app.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(note_id: int, db: DB) -> None:
    note = await db.get(Note, note_id)
    if not note:
        raise HTTPException(404, "not found")
    await db.delete(note)
