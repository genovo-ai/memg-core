#!/usr/bin/env python3
"""Minimal FastAPI server for memg-core local testing.

Endpoints:
  - POST /memories        -> add a memory (note/document/task)
  - GET  /search          -> graph-first search
  - GET  /graph_search    -> low-level graph search (optional)
  - GET  /memories/{id}   -> fetch by id
  - POST /seed/basic      -> seed note+document+task for the given user (demo)

This server avoids external embedding calls when MEMG_FAKE_EMBEDDINGS=true.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from memg_core.application.memory import (
    add_memory as core_add_memory,
    search_memories as core_search_memories,
    graph_search as core_graph_search,
    get_memory_by_id as core_get_by_id,
)
from memg_core.core_services.embeddings import GenAIEmbedder
from memg_core.database_services import KuzuInterface, QdrantInterface
from memg_core.models.core import Memory, MemoryType


class FakeEmbedder:
    """Deterministic local embedder for offline testing (no external calls)."""

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or int(os.getenv("EMBEDDING_DIMENSION_LEN", "128"))

    def get_embedding(self, text: str) -> list[float]:
        # Simple hash-based deterministic vector for local testing
        import hashlib

        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand/repeat digest to fill dim
        vals: list[int] = list(h)
        vec: list[float] = []
        i = 0
        while len(vec) < self.dim:
            vec.append((vals[i % len(vals)] / 255.0) * 2.0 - 1.0)
            i += 1
        return vec


def _select_embedder() -> GenAIEmbedder | FakeEmbedder:
    if os.getenv("MEMG_FAKE_EMBEDDINGS", "true").lower() == "true":
        return FakeEmbedder()
    return GenAIEmbedder()


class AddMemoryRequest(BaseModel):
    memory_type: str = Field(..., description="note|document|task")
    user_id: str
    content: str
    title: Optional[str] = None
    summary: Optional[str] = None
    due_date: Optional[str] = None  # ISO datetime for task
    tags: list[str] = Field(default_factory=list)


app = FastAPI(title="memg-core test server", version="0.1.0")


@app.post("/memories")
def add_memory(req: AddMemoryRequest) -> dict[str, Any]:
    try:
        try:
            mtype = MemoryType(req.memory_type)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid memory_type")

        created_at = datetime.now(UTC)
        due_dt = None
        if req.due_date:
            try:
                due_dt = datetime.fromisoformat(req.due_date)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid due_date format")

        mem = Memory(
            user_id=req.user_id,
            content=req.content,
            memory_type=mtype,
            title=req.title,
            summary=req.summary,
            tags=req.tags,
            created_at=created_at,
            due_date=due_dt,
        )

        # Storage interfaces (use defaults)
        qdrant = QdrantInterface()
        kuzu = KuzuInterface()
        embedder = _select_embedder()

        memory_id = core_add_memory(mem, qdrant=qdrant, kuzu=kuzu, embedder=embedder)
        return {"ok": True, "id": memory_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}")
async def get_memory(memory_id: str) -> dict[str, Any]:
    mem = await core_get_by_id(memory_id)
    if not mem:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "memory": mem.model_dump()}


@app.get("/search")
async def search(query: str, user_id: str, limit: int = 10) -> dict[str, Any]:
    embedder = _select_embedder()
    results = await core_search_memories(query, user_id, limit=limit, embedder=embedder)
    out = []
    for r in results:
        out.append(
            {
                "id": r.memory.id,
                "type": r.memory.memory_type.value,
                "title": r.memory.title,
                "content": r.memory.content,
                "score": r.score,
                "source": r.source,
            }
        )
    return {"ok": True, "results": out}


@app.get("/graph_search")
async def graph_search(query: str, user_id: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    results = await core_graph_search(query, user_id=user_id, limit=limit)
    return {
        "ok": True,
        "results": [
            {
                "id": r.memory.id,
                "type": r.memory.memory_type.value,
                "title": r.memory.title,
                "content": r.memory.content,
                "score": r.score,
                "source": r.source,
            }
            for r in results
        ],
    }


@app.post("/seed/basic")
def seed_basic(user_id: str = "demo_user") -> dict[str, Any]:
    embedder = _select_embedder()
    qdrant = QdrantInterface()
    kuzu = KuzuInterface()

    added: list[str] = []
    note = Memory(user_id=user_id, content="Use Redis for caching", memory_type=MemoryType.NOTE)
    added.append(core_add_memory(note, qdrant=qdrant, kuzu=kuzu, embedder=embedder))

    doc = Memory(
        user_id=user_id,
        content="PostgreSQL tuning guide...",
        summary="Guide for tuning Postgres",
        title="DB Tips",
        memory_type=MemoryType.DOCUMENT,
    )
    added.append(core_add_memory(doc, qdrant=qdrant, kuzu=kuzu, embedder=embedder))

    task = Memory(
        user_id=user_id,
        content="Implement cache invalidation",
        title="Cache invalidation",
        memory_type=MemoryType.TASK,
    )
    added.append(core_add_memory(task, qdrant=qdrant, kuzu=kuzu, embedder=embedder))

    return {"ok": True, "ids": added}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("FASTAPI_PORT", "8989"))
    uvicorn.run("scripts.fastapi_server:app", host="0.0.0.0", port=port, reload=False)
