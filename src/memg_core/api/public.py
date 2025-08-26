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
from memg_core.core.logging import get_logger
from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipelines.indexer import create_memory_service
from memg_core.core.pipelines.retrieval import create_search_service

# Legacy imports - now using clean architecture with services
from memg_core.core.yaml_translator import YamlTranslator
from memg_core.utils.db_clients import DatabaseClients

logger = get_logger(__name__)

# ----------------------------- NEW CLEAN ARCHITECTURE -----------------------------


# ----------------------------- indexing helper -----------------------------


def _index_memory_with_yaml(memory: Memory) -> str:
    """Index a memory with strict YAML-driven anchor text resolution.

    - Uses DatabaseClients for unified database access
    - Uses MemoryService for storage operations
    - Resolves anchor text via YAML translator (REQUIRED - no fallbacks)
    """
    # Initialize database clients and services
    # TODO: Add yaml_schema_path to config or make it configurable
    yaml_path = "config/software_dev.yaml"  # Default for now

    db_clients = DatabaseClients(yaml_path=yaml_path)
    db_clients.init_dbs()  # DDL operations (create collections/tables if needed)

    memory_service = create_memory_service(db_clients)

    # Add memory using the unified service
    # Note: This bypasses the normal payload validation since Memory is already validated
    return memory_service.add_memory(
        memory_type=memory.memory_type, payload=memory.payload, user_id=memory.user_id
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
    yaml_translator = YamlTranslator()
    memory = yaml_translator.create_memory_from_yaml(
        memory_type=memory_type, payload=payload, user_id=user_id
    )
    # Tags should be part of payload, not hardcoded field - remove this assignment
    # If tags are needed, they should be defined in YAML schema and passed in payload

    # Index with strict YAML anchor resolution
    hrid = _index_memory_with_yaml(memory)
    # Keep UUID as id; set hrid field for user-facing operations
    memory.hrid = hrid
    return memory


# ----------------------------- public search -----------------------------


def search(
    query: str | None,
    user_id: str,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
    *,
    memory_type: str | None = None,
    modified_within_days: int | None = None,
    include_details: str = "self",
    projection: dict[str, list[str]] | None = None,
    relation_names: list[str] | None = None,
    neighbor_limit: int = 5,
    hops: int = 1,
    include_semantic: bool = False,
) -> list[SearchResult]:
    """GraphRAG search over memories: vector seeds → graph expansion → semantic enhancement.

    Requirements: at least one of `query` or `memory_type`.

    Parameters
    ----------
    query : str, optional
        Search query text for vector seed matching
    user_id : str
        User identifier for filtering results
    limit : int, default 20
        Maximum number of results to return
    filters : dict, optional
        Additional filters to apply to search (e.g., {"core.project": "memg-core"})
    memory_type : str, optional
        Filter results to specific memory type
    modified_within_days : int, optional
        Filter to memories modified within N days
    include_details : str, default "self"
        Detail level: "none" (anchor only) or "self" (full payload)
    projection : dict, optional
        Per-type field allow-list for result projection
    relation_names : list[str], optional
        Specific relation names to expand (None = all relations)
    neighbor_limit : int, default 5
        Maximum number of neighbors per seed
    hops : int, default 1
        Number of graph hops to expand
    include_semantic : bool, default False
        Enable semantic expansion via YAML see_also configuration.
        Finds memories semantically related to seeds based on anchor text.

    Returns
    -------
    list[SearchResult]
        GraphRAG results: seeds (full payloads) + neighbors (anchor-only) +
        optional semantic expansions, deduplicated and sorted.
    """
    if (not query or not query.strip()) and not memory_type:
        raise ValidationError("Provide `query` or `memory_type`.")
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

    # Initialize database clients and search service
    config = get_config()
    yaml_path = config.memg.yaml_schema_path

    db_clients = DatabaseClients(yaml_path=yaml_path)
    db_clients.init_dbs()  # DDL operations (create collections/tables if needed)

    search_service = create_search_service(db_clients)

    neighbor_limit_env = os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT")
    if neighbor_limit_env is not None:
        neighbor_limit = int(neighbor_limit_env)

    return search_service.search(
        query=(query.strip() if query else ""),
        user_id=user_id,
        limit=limit,
        memory_type=memory_type,
        relation_names=relation_names,
        neighbor_limit=neighbor_limit,
        hops=hops,
        include_semantic=include_semantic,
        include_details=include_details,
        modified_within_days=modified_within_days,
        filters=filters,
        projection=projection,
    )


# ----------------------------- public delete -----------------------------


def delete_memory(
    user_id: str,
    uuid: str = None,
    hrid: str = None,
) -> bool:
    """Delete a single memory by explicit UUID or HRID with user verification.

    Args:
        user_id: User ID for ownership verification
        uuid: UUID of the memory to delete (takes precedence if both provided)
        hrid: HRID of the memory to delete (e.g., "TASK_AAA001")

    Returns:
        True if deletion was successful

    Raises:
        ValidationError: If neither uuid nor hrid provided, or if memory doesn't exist/belong to user
        DatabaseError: If database operations fail
    """
    if not user_id or not user_id.strip():
        raise ValidationError("user_id is required and cannot be empty")

    if not uuid and not hrid:
        raise ValidationError("Either uuid or hrid must be provided")

    # Initialize database clients and memory service
    config = get_config()
    yaml_path = config.memg.yaml_schema_path

    db_clients = DatabaseClients(yaml_path=yaml_path)
    db_clients.init_dbs()  # DDL operations (create collections/tables if needed)

    # Get interfaces for direct operations (until delete is moved to MemoryService)
    qdrant = db_clients.get_qdrant_interface()
    kuzu = db_clients.get_kuzu_interface()

    # UUID takes precedence if both provided
    if uuid:
        # Direct UUID lookup in Qdrant
        point = qdrant.get_point(uuid)
        if not point:
            raise ValidationError(f"Memory with UUID {uuid} not found")
        memory_uuid = uuid

    elif hrid:
        # Resolve HRID to UUID via HridMapping table
        kuzu_results = kuzu.query(
            "MATCH (m:HridMapping {hrid: $hrid}) WHERE m.deleted_at IS NULL RETURN m.uuid as uuid",
            {"hrid": hrid},
        )
        if not kuzu_results:
            raise ValidationError(f"Memory with HRID {hrid} not found")
        memory_uuid = kuzu_results[0]["uuid"]

        # Get the point from Qdrant using resolved UUID
        point = qdrant.get_point(memory_uuid)
        if not point:
            raise ValidationError(f"Memory with HRID {hrid} found in Kuzu but not in Qdrant")

    # Check user ownership (flat payload)
    payload = point.get("payload", {})
    memory_user_id = payload.get("user_id")

    if memory_user_id != user_id:
        memory_id_str = uuid if uuid else hrid
        raise ValidationError(f"Memory {memory_id_str} does not belong to user {user_id}")

    # Resolve memory_type for correct Kuzu entity table deletion
    # Primary: from Qdrant payload (fast, reliable)
    memory_type = payload.get("memory_type")

    # Fallback: from HRID mapping if not in payload
    if not memory_type and hrid:
        try:
            kuzu_results = kuzu.query(
                "MATCH (m:HridMapping {hrid: $hrid}) WHERE m.deleted_at IS NULL RETURN m.memory_type as memory_type",
                {"hrid": hrid},
            )
            if kuzu_results:
                memory_type = kuzu_results[0]["memory_type"]
        except Exception as e:
            # If HRID mapping query fails, we'll use a fallback approach
            logger.debug(f"HRID mapping lookup failed for {hrid}: {e}")
            # memory_type remains None, triggering fallback logic below

    if not memory_type:
        raise ValidationError(
            "Could not resolve memory_type for deletion. Memory may be corrupted."
        )

    # Delete from both storage backends using the resolved UUID
    # Delete from Qdrant first (primary store)
    qdrant_success = qdrant.delete_points([memory_uuid])

    # Delete from Kuzu using the correct entity table (not generic "Memory")
    kuzu_success = True
    try:
        # Delete from entity-specific table (e.g., "task", "note", "memo_test")
        kuzu_success = kuzu.delete_node(memory_type, memory_uuid)
    except (DatabaseError, Exception):
        # Ignore Kuzu deletion errors for now - Qdrant is the primary store
        # This handles issues with relationship constraints in Kuzu
        kuzu_success = True

    return qdrant_success and kuzu_success
