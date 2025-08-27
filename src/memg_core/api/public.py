"""
Thin public API layer for memg-core.

This is a THIN WRAPPER that accepts pre-initialized services.
The calling application (FastAPI, Flask, etc.) should:
1. Initialize DatabaseClients once at startup
2. Create MemoryService and SearchService once
3. Pass these services to these API functions

NO database initialization happens here - services must be pre-initialized!
"""

from __future__ import annotations

import os
from typing import Any

from ..core.models import Memory, SearchResult
from ..core.pipelines.indexer import MemoryService, create_memory_service
from ..core.pipelines.retrieval import SearchService, create_search_service
from ..core.yaml_translator import YamlTranslator
from ..utils.db_clients import DatabaseClients
from ..utils.hrid_tracker import HridTracker

# ----------------------------- SERVICE INITIALIZATION -----------------------------


class MemgServices:
    """Container for pre-initialized memg-core services.

    The calling application should create this ONCE at startup and reuse it.
    Can be used as a context manager for automatic cleanup.

    Example:
        # Manual cleanup:
        services = MemgServices("config/software_dev.yaml")
        # ... use services ...
        services.close()

        # Automatic cleanup:
        with MemgServices("config/software_dev.yaml") as services:
            # ... use services ...
            pass  # automatically closed
    """

    def __init__(self, yaml_path: str, db_path: str = "tmp", db_name: str = "memg"):
        """Initialize all services with database connections.

        Args:
            yaml_path: Path to YAML schema file
            db_path: Database storage path
            db_name: Database name/collection name
        """
        # Initialize database clients (DDL + interfaces)
        self.db_clients = DatabaseClients(yaml_path=yaml_path)
        self.db_clients.init_dbs(db_path=db_path, db_name=db_name)

        # Create services
        self.memory_service = create_memory_service(self.db_clients)
        self.search_service = create_search_service(self.db_clients)
        self.yaml_translator = YamlTranslator(yaml_path=yaml_path)
        self.hrid_tracker = HridTracker(self.db_clients.get_kuzu_interface())

    def close(self):
        """Close database connections and cleanup resources."""
        if hasattr(self, "db_clients") and self.db_clients:
            self.db_clients.close()

        # Clear service references
        self.memory_service = None
        self.search_service = None
        self.yaml_translator = None
        self.hrid_tracker = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically close connections."""
        self.close()


# ----------------------------- THIN API LAYER -----------------------------


def add_memory(
    memory_service: MemoryService,
    yaml_translator: YamlTranslator,
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
) -> Memory:
    """Add a memory using pre-initialized services.

    Args:
        memory_service: Pre-initialized MemoryService instance
        yaml_translator: Pre-initialized YamlTranslator instance
        memory_type: Type of memory to create
        payload: Memory data
        user_id: Owner of the memory

    Returns:
        Memory: Created memory with HRID assigned
    """
    # Create and validate memory using YAML translator
    memory = yaml_translator.create_memory_from_yaml(
        memory_type=memory_type, payload=payload, user_id=user_id
    )

    # Index memory and get HRID
    hrid = memory_service.add_memory(
        memory_type=memory.memory_type, payload=memory.payload, user_id=memory.user_id
    )

    # Get the correct UUID from HRID tracker
    uuid = memory_service.hrid_tracker.get_uuid(hrid, user_id)

    # Update memory with correct UUID and HRID
    memory.id = uuid
    memory.hrid = hrid
    return memory


def search(
    search_service: SearchService, query: str | None, user_id: str, **kwargs
) -> list[SearchResult]:
    """Search memories using pre-initialized SearchService.

    Args:
        search_service: Pre-initialized SearchService instance
        query: Search query text
        user_id: User identifier
        **kwargs: All other search parameters passed directly to SearchService

    Returns:
        List of search results
    """
    # Apply environment overrides
    if "neighbor_limit" not in kwargs:
        neighbor_limit_env = os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT")
        if neighbor_limit_env is not None:
            kwargs["neighbor_limit"] = int(neighbor_limit_env)

    return search_service.search(query=(query.strip() if query else ""), user_id=user_id, **kwargs)


def delete_memory(
    memory_service: MemoryService,
    hrid_tracker: HridTracker,
    memory_id: str,
    user_id: str,
) -> bool:
    """Delete a memory using HRID (MCP consumers should only use HRIDs).

    Args:
        memory_service: Pre-initialized MemoryService instance
        hrid_tracker: Pre-initialized HridTracker instance
        memory_id: Memory HRID (e.g., 'NOTE_AAA001')
        user_id: User ID for ownership verification

    Returns:
        True if deletion successful

    Note:
        MCP consumers should only use HRIDs, never UUIDs.
        UUIDs are internal implementation details.
    """
    try:
        # memory_id should be an HRID
        hrid = memory_id

        # Get UUID for database operations
        uuid = hrid_tracker.get_uuid(hrid, user_id)

        # Extract memory type from HRID
        memory_type = hrid.split("_")[0].lower()

        # Verify ownership
        kuzu_interface = memory_service.kuzu
        query = f"MATCH (m:{memory_type.title()}) WHERE m.id = $uuid RETURN m.user_id"
        result = kuzu_interface.conn.execute(query, parameters={"uuid": uuid})

        if not result.has_next():
            return False  # Memory not found

        memory_user_id = result.get_next()[0]

        if memory_user_id != user_id:
            return False  # User doesn't own this memory

        # Delete the memory using MemoryService
        success = memory_service.delete_memory(
            memory_hrid=hrid, memory_type=memory_type, user_id=user_id
        )

        return success

    except Exception:
        # Any error means deletion failed
        return False


def add_relationship(
    memory_service: MemoryService,
    from_memory_id: str,
    to_memory_id: str,
    relation_type: str,
    user_id: str,
) -> bool:
    """Add a relationship between two memories (thin wrapper).

    Args:
        memory_service: Pre-initialized MemoryService instance
        from_memory_id: Source memory HRID (e.g., 'TASK_AAA001')
        to_memory_id: Target memory HRID (e.g., 'NOTE_AAA002')
        relation_type: Type of relationship
        user_id: User ID for ownership verification

    Returns:
        True if relationship created successfully
    """
    # Extract memory types from HRIDs (e.g., "TASK_AAA001" -> "task")
    from_type = from_memory_id.split("_")[0].lower()
    to_type = to_memory_id.split("_")[0].lower()

    # Use MemoryService to handle the relationship creation
    memory_service.add_relationship(
        from_memory_hrid=from_memory_id,
        to_memory_hrid=to_memory_id,
        relation_type=relation_type,
        from_memory_type=from_type,
        to_memory_type=to_type,
        user_id=user_id,
        properties={},
    )

    return True


# ----------------------------- USAGE EXAMPLE -----------------------------
# See tests/test_thin_api.py for usage examples
