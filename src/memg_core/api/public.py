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
from pathlib import Path
from typing import Any

from ..core.models import SearchResult
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


# ----------------------------- ENVIRONMENT-BASED API -----------------------------


def get_services() -> tuple[MemoryService, SearchService, YamlTranslator]:
    """Get services from environment variables - eliminates redundancy."""
    yaml_path = os.environ.get("YAML_PATH", "config/core.memo.yaml")
    kuzu_path = os.environ.get("KUZU_DB_PATH", "tmp/memg")

    # Extract db_name and db_path from kuzu_path
    kuzu_path_obj = Path(kuzu_path)
    db_name = kuzu_path_obj.stem
    db_path = str(kuzu_path_obj.parent)

    # Create services
    db_clients = DatabaseClients(yaml_path=yaml_path)
    db_clients.init_dbs(db_path=db_path, db_name=db_name)

    memory_service = create_memory_service(db_clients)
    search_service = create_search_service(db_clients)
    yaml_translator = YamlTranslator(yaml_path=yaml_path)

    return memory_service, search_service, yaml_translator


def add_memory(
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
) -> str:
    """Add a memory and return HRID.

    Args:
        memory_type: Type of memory to create (note, document, memo)
        payload: Memory data conforming to YAML schema
        user_id: Owner of the memory

    Returns:
        str: HRID of created memory (never exposes UUID)
    """
    memory_service, _, _ = get_services()

    # Add memory and return HRID directly
    hrid = memory_service.add_memory(memory_type=memory_type, payload=payload, user_id=user_id)

    return hrid


def search(
    query: str, user_id: str, memory_type: str | None = None, limit: int = 10, **kwargs
) -> list[SearchResult]:
    """Search memories and return results.

    Args:
        query: Search query text
        user_id: User identifier
        memory_type: Optional memory type filter
        limit: Maximum number of results
        **kwargs: Additional search parameters

    Returns:
        List of search results with HRIDs (no UUIDs exposed)
    """
    _, search_service, _ = get_services()

    # Clean query and add common parameters
    clean_query = query.strip() if query else ""
    search_params = {"memory_type": memory_type, "limit": limit, **kwargs}

    return search_service.search(query=clean_query, user_id=user_id, **search_params)


def delete_memory(
    hrid: str,
    user_id: str,
) -> bool:
    """Delete a memory using HRID.

    Args:
        hrid: Memory HRID (e.g., 'NOTE_AAA001')
        user_id: User ID for ownership verification

    Returns:
        True if deletion successful, False otherwise
    """
    memory_service, _, _ = get_services()

    try:
        # Extract memory type from HRID (e.g., "NOTE_AAA001" -> "note")
        memory_type = hrid.split("_")[0].lower()
        return memory_service.delete_memory(hrid, memory_type, user_id)
    except Exception:
        return False
