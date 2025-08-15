"""
Strict YAML-enforced public API exposing only generic add_memory and unified search.
- Uses YAML translator to validate ALL payloads against dynamically generated Pydantic models
- NO hardcoded helper functions - clients MUST use YAML schema directly
- All validation is strict - no fallbacks, no backward compatibility
- search() supports vector-first, graph-first, or hybrid via `mode`
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from memg_core.core.config import get_config
from memg_core.core.exceptions import ValidationError
from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search
from memg_core.core.yaml_translator import build_anchor_text, get_entity_model

# ----------------------------- indexing helper -----------------------------


def _index_memory_with_yaml(memory: Memory) -> str:
    """Index a memory with strict YAML-driven anchor text resolution.

    - Initializes interfaces using config/env
    - Resolves anchor text via YAML translator (REQUIRED - no fallbacks)
    - Upserts into Qdrant and mirrors to Kuzu
    """
    config = get_config()

    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    # Strict YAML anchor text resolution - no fallbacks
    index_text_override = build_anchor_text(memory)

    return add_memory_index(
        memory,
        qdrant,
        kuzu,
        embedder,
        index_text_override=index_text_override,
    )


# ----------------------------- public adders -----------------------------


def add_memory(
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
    tags: list[str] | None = None,
) -> Memory:
    """Create a memory using strict YAML schema validation and index it.

    Validates payload against dynamically generated Pydantic model from YAML schema.
    NO fallbacks, NO backward compatibility.
    """
    # Get dynamic Pydantic model and validate payload in one step
    entity_model = get_entity_model(memory_type)
    try:
        validated_entity = entity_model(**payload)
    except PydanticValidationError as e:
        raise ValidationError(f"Validation failed for '{memory_type}': {e}") from e

    # Create Memory with validated payload
    memory = Memory(
        memory_type=memory_type,
        payload=validated_entity.model_dump(exclude_none=True),
        user_id=user_id,
        tags=tags or [],
    )

    # Index with strict YAML anchor resolution
    memory.id = _index_memory_with_yaml(memory)
    return memory


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
    include_details: str = "self",  # NEW: "none" | "self" (neighbors remain anchors-only in v1)
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
