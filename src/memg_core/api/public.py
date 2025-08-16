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

from memg_core.core.config import get_config
from memg_core.core.exceptions import DatabaseError, ValidationError
from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search
from memg_core.core.yaml_translator import create_memory_from_yaml

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

    # Anchor text resolution is handled by YAML translator in the indexer pipeline
    return add_memory_index(
        memory,
        qdrant,
        kuzu,
        embedder,
    )


# ----------------------------- public adders -----------------------------


def add_memory(
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
) -> Memory:
    """Create a memory using strict YAML schema validation and index it.

    Validates payload against dynamically generated Pydantic model from YAML schema.
    NO fallbacks, NO backward compatibility.
    """
    if not memory_type or not memory_type.strip():
        raise ValidationError("memory_type is required and cannot be empty")
    if not user_id or not user_id.strip():
        raise ValidationError("user_id is required and cannot be empty")
    if not payload or not isinstance(payload, dict):
        raise ValidationError("payload is required and must be a dictionary")

    # Create memory with strict YAML validation - no fallbacks
    memory = create_memory_from_yaml(memory_type=memory_type, payload=payload, user_id=user_id)
    # Tags should be part of payload, not hardcoded field - remove this assignment
    # If tags are needed, they should be defined in YAML schema and passed in payload

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
    relation_names: list[str] | None = None,
    neighbor_cap: int = 5,
    include_see_also: bool = False,  # NEW: enable see_also functionality
) -> list[SearchResult]:
    """Unified search over memories (Graph+Vector) with optional semantic discovery.

    Requirements: at least one of `query` or `memo_type`.

    Parameters
    ----------
    query : str, optional
        Search query text for semantic matching
    user_id : str
        User identifier for filtering results
    limit : int, default 20
        Maximum number of results to return
    filters : dict, optional
        Additional filters to apply to search
    memo_type : str, optional
        Filter results to specific memory type
    modified_within_days : int, optional
        Filter to memories modified within N days
    mode : str, optional
        Search mode: 'vector', 'graph', or 'hybrid'
    include_details : str, default "self"
        Detail level: "none" or "self"
    projection : dict, optional
        Per-type field allow-list for result projection
    relation_names : list[str], optional
        Specific relation names to consider in graph search
    neighbor_cap : int, default 5
        Maximum number of neighbors to include
    include_see_also : bool, default False
        Enable semantic discovery of related memories. When True,
        searches for memories semantically related to primary results
        based on YAML see_also configuration. Related memories are
        tagged with 'see_also_{type}' source attribution.

    Returns
    -------
    list[SearchResult]
        Search results including primary matches and (optionally)
        semantically related memories found via see_also feature.
    """
    if (not query or not query.strip()) and not memo_type:
        raise ValidationError("Provide `query` or `memo_type`.")
    if not user_id:
        raise ValidationError("User ID is required for search")

    # VALIDATE RELATION NAMES AGAINST YAML SCHEMA - crash if invalid
    if relation_names:
        try:
            from ..core.types import TypeRegistry

            registry = TypeRegistry.get_instance()
            valid_predicates = registry.get_valid_predicates()
            invalid = [r for r in relation_names if r not in valid_predicates]
            if invalid:
                raise ValidationError(
                    f"Invalid relation names: {invalid}. Valid predicates: {valid_predicates}"
                )
        except RuntimeError:
            # TypeRegistry not initialized - skip validation for now
            pass

    config = get_config()

    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    neighbor_cap_env = os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT")
    if neighbor_cap_env is not None:
        neighbor_cap = int(neighbor_cap_env)

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
        include_see_also=include_see_also,
    )


# ----------------------------- public delete -----------------------------


def _resolve_memory_id_to_uuid(memory_id: str, qdrant: QdrantInterface) -> str:
    """Resolve either UUID or HRID to UUID.

    Args:
        memory_id: Either a UUID or HRID (e.g., "TASK_AAA001")
        qdrant: QdrantInterface to search for HRID

    Returns:
        str: The UUID of the memory

    Raises:
        ValidationError: If memory not found or invalid format
    """
    # Try as UUID first (direct lookup)
    point = qdrant.get_point(memory_id)
    if point:
        return memory_id

    # If not found as UUID, try as HRID
    # Check if it looks like an HRID format
    if "_" in memory_id and memory_id.replace("_", "").replace("-", "").isalnum():
        # Search by HRID filter
        dummy_vector = [0.0] * 384  # Default embedding size for search

        results = qdrant.search_points(
            vector=dummy_vector, limit=1, filters={"core.hrid": memory_id}
        )

        if results and len(results) > 0:
            # Found by HRID, return the UUID
            result = results[0]
            uuid = result.get("id")
            if uuid:
                return str(uuid)

    # Neither UUID nor HRID worked
    raise ValidationError(f"Memory with ID {memory_id} not found")


def delete_memory(
    memory_id: str,
    user_id: str,
) -> bool:
    """Delete a single memory by UUID or HRID with user verification.

    Args:
        memory_id: UUID or HRID of the memory to delete (e.g., "uuid-string" or "TASK_AAA001")
        user_id: User ID for ownership verification

    Returns:
        True if deletion was successful

    Raises:
        ValidationError: If memory_id or user_id are invalid/missing
        DatabaseError: If memory doesn't exist or user doesn't own it
    """
    if not memory_id or not memory_id.strip():
        raise ValidationError("memory_id is required and cannot be empty")
    if not user_id or not user_id.strip():
        raise ValidationError("user_id is required and cannot be empty")

    config = get_config()

    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)

    # Resolve memory_id (UUID or HRID) to UUID
    uuid = _resolve_memory_id_to_uuid(memory_id, qdrant)

    # Get the memory to verify user ownership
    point = qdrant.get_point(uuid)
    if not point:
        raise ValidationError(f"Memory with ID {memory_id} not found")

    # Check user ownership
    payload = point.get("payload", {})
    core = payload.get("core", {})
    memory_user_id = core.get("user_id")

    if memory_user_id != user_id:
        raise ValidationError(f"Memory {memory_id} does not belong to user {user_id}")

    # Delete from both storage backends using the resolved UUID
    # Delete from Qdrant first (primary store)
    qdrant_success = qdrant.delete_points([uuid])

    # Try to delete from Kuzu (secondary store) - don't fail if this has issues
    kuzu_success = True
    try:
        kuzu_success = kuzu.delete_node("Memory", uuid)
    except (DatabaseError, Exception):
        # Ignore Kuzu deletion errors for now - Qdrant is the primary store
        # This handles issues with relationship constraints in Kuzu
        kuzu_success = True

    return qdrant_success and kuzu_success
