# scripts/fastapi_server.py
"""
FastAPI convenience wrapper for memg-core - NOT part of core API!
This is a development/testing tool, similar to FastMCP.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from memg_core.api.public import add_memory as public_add_memory, search as public_search
from memg_core.core.models import Memory, SearchResult

# ----------------------------- FastAPI app -----------------------------

app = FastAPI(
    title="memg-core FastAPI Wrapper",
    version="0.1.0",
    description=(
        "Development/testing FastAPI wrapper over memg-core public API.\n"
        "This is NOT part of the core - it's a convenience script like FastMCP."
    ),
)


# ----------------------------- Schemas -----------------------------


class HealthResponse(BaseModel):
    status: str = "ok"


class SearchRequest(BaseModel):
    query: str | None = Field(
        default=None,
        description="Search text. If omitted, you must provide memo_type/filters/date upstream.",
    )
    user_id: str
    limit: int = 20
    filters: dict[str, Any] | None = None
    relation_names: list[str] | None = None
    neighbor_cap: int = 5
    # new knobs (already supported in core/retrieval via public.search wiring)
    include_details: str = Field(default="none", description='One of: "none" (default), "self"')
    projection: dict[str, list[str]] | None = Field(
        default=None,
        description='Per-type allowlist for payload fields, e.g. {"my_type": ["field1", "field2"]}',
    )
    # passthrough (keyword-only in core; accepted here and forwarded)
    memo_type: str | None = None
    modified_within_days: int | None = None
    mode: str | None = Field(
        default=None, description='Optional override: "vector" | "graph" | "hybrid"'
    )


class AddMemoryRequest(BaseModel):
    type: str
    statement: str
    payload: dict[str, Any]
    user_id: str
    tags: list[str] | None = None


# ----------------------------- Routes -----------------------------


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.post("/v1/memories", response_model=Memory)
def add_memory(req: AddMemoryRequest) -> Memory:
    """Generic memory addition using YAML-defined types"""
    try:
        # The public API now expects statement as a top-level argument.
        # The payload should only contain the YAML-defined fields.
        full_payload = {"statement": req.statement, **req.payload}
        return public_add_memory(
            memory_type=req.type,
            payload=full_payload,
            user_id=req.user_id,
            tags=req.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/v1/search", response_model=list[SearchResult])
def search_memories(req: SearchRequest) -> list[SearchResult]:
    """Search memories with unified retrieval"""
    try:
        if not req.query and not req.memo_type:
            raise HTTPException(status_code=400, detail="Query or memo_type is required.")
        return public_search(
            query=req.query,
            user_id=req.user_id,
            limit=req.limit,
            filters=req.filters,
            relation_names=req.relation_names,
            neighbor_cap=req.neighbor_cap,
            memo_type=req.memo_type,
            modified_within_days=req.modified_within_days,
            mode=req.mode,
            include_details=req.include_details,
            projection=req.projection,
        )
    except Exception as e:
        # surface validation errors cleanly
        raise HTTPException(status_code=400, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
