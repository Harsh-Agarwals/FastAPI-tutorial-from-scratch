"""
Chapter 31 — System Design Notes.

This chapter is intentionally markdown-heavy. The "app" is a tiny
health endpoint so the folder is still a runnable FastAPI app.

Run:
    uvicorn 31_system_design_notes.app:app --reload --port 8000
"""
from fastapi import FastAPI

app = FastAPI(title="Chapter 31 — System Design Notes")


@app.get("/")
def root() -> dict:
    return {"chapter": "31_system_design_notes", "see": "README.md"}
