# scripts/fastai_example.py - Development/Testing FastAPI Example
# Note: The production server is at src/memg_core/api/server.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from memg_core.api.public import (
    add_document as public_add_document,
    add_memory as public_add_memory,
    add_note as public_add_note,
    add_task as public_add_task,
    search as public_search,
)
from memg_core.core.models import Memory, SearchResult


# ----------------------------- FastAPI app -----------------------------

app = FastAPI(
    title="memg-core API (Development Example)",
    version="0.1.0",
    description=(
        "Development/testing FastAPI example.\n"
        "For production, use: src/memg_core/api/server.py"
    ),
)


# ----------------------------- Schemas -----------------------------

class HealthResponse(BaseModel):
    status: str = "ok"


class SearchRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Search text. If omitted, you must provide memo_type/filters/date upstream.")
    user_id: str
    limit: int = 20
    filters: Optional[Dict[str, Any]] = None
    relation_names: Optional[List[str]] = None
    neighbor_cap: int = 5
    # new knobs (already supported in core/retrieval via public.search wiring)
    include_details: str = Field(default="none", description='One of: "none" (default), "self"')
    projection: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description='Per-type allowlist, e.g. {"document": ["title", "summary"]}',
    )
    # passthrough (keyword-only in core; accepted here and forwarded)
    memo_type: Optional[str] = None
    modified_within_days: Optional[int] = None
    mode: Optional[str] = Field(default=None, description='Optional override: "vector" | "graph" | "hybrid"')


class AddNoteRequest(BaseModel):
    text: str
    user_id: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None


class AddDocumentRequest(BaseModel):
    text: str
    user_id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None


class AddTaskRequest(BaseModel):
    text: str
    user_id: str
    title: Optional[str] = None
    due_date: Optional[datetime] = None  # ISO 8601 -> datetime
    tags: Optional[List[str]] = None


class AddMemoryRequest(BaseModel):
    memory_type: str
    payload: Dict[str, Any]
    user_id: str
    tags: Optional[List[str]] = None


# ----------------------------- Routes -----------------------------

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/v1/search", response_model=List[SearchResult])
def search(req: SearchRequest) -> List[SearchResult]:
    try:
        return public_search(
            query=req.query,
            user_id=req.user_id,
            limit=req.limit,
            filters=req.filters,
            memo_type=req.memo_type,
            modified_within_days=req.modified_within_days,
            mode=req.mode,
            include_details=req.include_details,
            projection=req.projection,
        )
    except Exception as e:
        # surface validation errors cleanly
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/memories/note", response_model=Memory)
def add_note(req: AddNoteRequest) -> Memory:
    try:
        return public_add_note(req.text, user_id=req.user_id, title=req.title, tags=req.tags)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/memories/document", response_model=Memory)
def add_document(req: AddDocumentRequest) -> Memory:
    try:
        return public_add_document(
            req.text,
            user_id=req.user_id,
            title=req.title,
            summary=req.summary,
            tags=req.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/memories/task", response_model=Memory)
def add_task(req: AddTaskRequest) -> Memory:
    try:
        # pass through due_date as-is; public.add_task handles datetime | None
        return public_add_task(
            req.text,
            user_id=req.user_id,
            title=req.title,
            due_date=req.due_date,  # now a datetime | None as expected
            tags=req.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/memories", response_model=Memory)
def add_memory(req: AddMemoryRequest) -> Memory:
    try:
        return public_add_memory(
            memory_type=req.memory_type,
            payload=req.payload,
            user_id=req.user_id,
            tags=req.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
