"""
Minimal public API exposing generic add_memory and unified search.
- Uses YAML translator to validate payloads and resolve anchor → statement.
- add_note/add_document/add_task are thin shims that build normalized payloads
  with `statement` as the anchor and optional `details`.
- search() supports vector-first, graph-first, or hybrid via `mode`, and
  accepts date scoping via `modified_within_days`.
"""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any

from memg_core.core.config import get_config
from memg_core.core.exceptions import ValidationError
from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search
from memg_core.core.yaml_translator import build_anchor_text, create_memory_from_yaml

# ----------------------------- indexing helper -----------------------------


def _index_memory_with_optional_yaml(memory: Memory) -> str:
    """Helper to index a memory with YAML-driven anchor if available.

    - Initializes interfaces using config/env.
    - Resolves anchor text via YAML translator (fallback suppressed).
    - Upserts into Qdrant and mirrors to Kuzu.
    """
    config = get_config()

    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    index_text_override = None
    try:
        index_text_override = build_anchor_text(memory)
    except Exception:
        # If YAML not configured or anchor missing, allow indexer to fail if truly empty
        index_text_override = None

    return add_memory_index(
        memory,
        qdrant,
        kuzu,
        embedder,
        index_text_override=index_text_override,
    )


# ----------------------------- public adders -----------------------------


def add_note(
    text: str,
    user_id: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a note-type memory (anchor = `statement`)."""
    if not text or not text.strip():
        raise ValidationError("Note content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    payload: dict[str, Any] = {
        "statement": text.strip(),
        "source": "user",
    }
    if title:
        payload["title"] = title

    return add_memory("note", payload, user_id, tags)


def add_document(
    text: str,
    user_id: str,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a document-type memory.

    Normalization:
    - `statement` = provided summary or truncated text
    - `details`   = full text body
    """
    if not text or not text.strip():
        raise ValidationError("Document content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    text_clean = text.strip()
    payload: dict[str, Any] = {
        "statement": (
            summary.strip()
            if summary and summary.strip()
            else (text_clean[:200] + "..." if len(text_clean) > 200 else text_clean)
        ),
        "details": text_clean,
        "source": "user",
    }
    if title:
        payload["title"] = title

    return add_memory("document", payload, user_id, tags)


def add_task(
    text: str,
    user_id: str,
    title: str | None = None,
    due_date: datetime | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a task-type memory (anchor = `statement`, with lifecycle fields)."""
    if not text or not text.strip():
        raise ValidationError("Task content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    payload: dict[str, Any] = {
        "statement": text.strip(),
        "source": "user",
        "status": "OPEN",
    }
    if title:
        payload["title"] = title
    if due_date:
        payload["due_date"] = due_date

    return add_memory("task", payload, user_id, tags)


# ----------------------------- public search -----------------------------


def search(
    query: str | None,
    user_id: str,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
    *,
    memo_type: str | None = None,
    modified_within_days: int | None = None,
    mode: str | None = None,  # 'vector' | 'graph' | 'hybrid'
    include_details: str = "none",  # NEW: "none" | "self" (neighbors remain anchors-only in v1)
    projection: dict[str, list[str]] | None = None,  # NEW: per-type field allow-list
) -> list[SearchResult]:
    """Unified search over memories (Graph+Vector).

    Requirements: at least one of `query` or `memo_type`.
    """
    if (not query or not query.strip()) and not memo_type:
        raise ValidationError("Provide `query` or `memo_type`.")
    if not user_id:
        raise ValidationError("User ID is required for search")

    config = get_config()

    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    # Optional relation whitelist from YAML registry (if present)
    relation_names = None
    if os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() == "true":
        try:
            from ..plugins.yaml_schema import get_relation_names

            relation_names = get_relation_names()
        except Exception:
            relation_names = None

    neighbor_cap = int(os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "5"))

    return graph_rag_search(
        query=(query.strip() if query else None),
        user_id=user_id,
        limit=limit,
        qdrant=qdrant,
        kuzu=kuzu,
        embedder=embedder,
        filters=filters,
        relation_names=relation_names,
        neighbor_cap=neighbor_cap,
        memo_type=memo_type,
        modified_within_days=modified_within_days,
        mode=mode,
        include_details=include_details,
        projection=projection,
    )


# ----------------------------- generic add -----------------------------


def add_memory(
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
    tags: list[str] | None = None,
) -> Memory:
    """Create a memory using YAML-defined type + payload and index it.

    Normalizes tags, validates against YAML, builds anchor via translator,
    and indexes into both stores. Returns the populated Memory.
    """
    if not memory_type or not memory_type.strip():
        raise ValidationError("Memory type cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")
    if not payload:
        raise ValidationError("Payload cannot be empty")

    # Merge tags without mutating original
    if tags:
        payload = dict(payload)
        existing = payload.get("tags", [])
        payload["tags"] = list({*existing, *tags})

    memory = create_memory_from_yaml(memory_type.strip(), payload, user_id)

    # Index and attach id
    memory.id = _index_memory_with_optional_yaml(memory)
    return memory
