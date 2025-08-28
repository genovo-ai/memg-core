"""
Public API for memg-core - designed for long-running servers.

Provides MemgClient for explicit initialization and module-level functions for
environment-based usage.
"""

from __future__ import annotations

import os
from typing import Any

from ..core.exceptions import DatabaseError, ProcessingError, ValidationError
from ..core.logging import get_logger
from ..core.models import SearchResult
from ..core.pipelines.indexer import MemoryService, create_memory_service
from ..core.pipelines.retrieval import SearchService, create_search_service
from ..core.yaml_translator import YamlTranslator
from ..utils.db_clients import DatabaseClients


class MemgClient:
    """Client for memg-core operations - initialize once, use throughout server lifetime."""

    def __init__(self, yaml_path: str, db_path: str):
        """Initialize client for long-running server usage."""
        self._db_clients = DatabaseClients(yaml_path=yaml_path)
        self._db_clients.init_dbs(db_path=db_path, db_name=self._db_clients.db_name)

        self._memory_service = create_memory_service(self._db_clients)
        self._search_service = create_search_service(self._db_clients)

        if not all([self._memory_service, self._search_service]):
            raise RuntimeError("Failed to initialize memg-core services")

    def add_memory(self, memory_type: str, payload: dict[str, Any], user_id: str) -> str:
        """Add memory and return HRID."""
        return self._memory_service.add_memory(memory_type, payload, user_id)

    def search(
        self, query: str, user_id: str, memory_type: str | None = None, limit: int = 10, **kwargs
    ) -> list[SearchResult]:
        """Search memories."""
        clean_query = query.strip() if query else ""
        return self._search_service.search(
            clean_query, user_id, memory_type=memory_type, limit=limit, **kwargs
        )

    def delete_memory(self, hrid: str, user_id: str, memory_type: str | None = None) -> bool:
        """Delete memory by HRID."""
        try:
            if memory_type is None:
                memory_type = hrid.split("_")[0].lower()
            return self._memory_service.delete_memory(hrid, memory_type, user_id)
        except (ProcessingError, DatabaseError, ValidationError) as e:
            # Log the specific error but return False for API compatibility
            logger = get_logger("memg_client")
            logger.warning(f"Delete memory failed for HRID {hrid}: {e}")
            return False

    def add_relationship(
        self,
        from_memory_hrid: str,
        to_memory_hrid: str,
        relation_type: str,
        from_memory_type: str,
        to_memory_type: str,
        user_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add relationship between memories."""
        self._memory_service.add_relationship(
            from_memory_hrid,
            to_memory_hrid,
            relation_type,
            from_memory_type,
            to_memory_type,
            user_id,
            properties,
        )

    def close(self):
        """Close client and cleanup resources."""
        if hasattr(self, "_db_clients") and self._db_clients:
            self._db_clients.close()


# ----------------------------- ENVIRONMENT-BASED SINGLETON API -----------------------------

_CLIENT: MemgClient | None = None


def _get_client() -> MemgClient:
    """Get or create singleton client from environment variables."""
    global _CLIENT
    if _CLIENT is None:
        yaml_path = os.environ.get("MEMG_YAML_PATH")
        db_path = os.environ.get("MEMG_DB_PATH")

        if not yaml_path or not db_path:
            raise RuntimeError("MEMG_YAML_PATH and MEMG_DB_PATH environment variables must be set")

        _CLIENT = MemgClient(yaml_path, db_path)
    return _CLIENT


def add_memory(memory_type: str, payload: dict[str, Any], user_id: str) -> str:
    """Add memory using environment-based client."""
    return _get_client().add_memory(memory_type, payload, user_id)


def search(
    query: str, user_id: str, memory_type: str | None = None, limit: int = 10, **kwargs
) -> list[SearchResult]:
    """Search memories using environment-based client."""
    return _get_client().search(query, user_id, memory_type, limit, **kwargs)


def delete_memory(hrid: str, user_id: str, memory_type: str | None = None) -> bool:
    """Delete memory using environment-based client."""
    return _get_client().delete_memory(hrid, user_id, memory_type)


def add_relationship(
    from_memory_hrid: str,
    to_memory_hrid: str,
    relation_type: str,
    from_memory_type: str,
    to_memory_type: str,
    user_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    """Add relationship using environment-based client."""
    _get_client().add_relationship(
        from_memory_hrid,
        to_memory_hrid,
        relation_type,
        from_memory_type,
        to_memory_type,
        user_id,
        properties,
    )


def shutdown_services():
    """Shutdown singleton client."""
    global _CLIENT
    if _CLIENT:
        _CLIENT.close()
        _CLIENT = None


# Legacy compatibility for MCP server
def get_services() -> tuple[MemoryService, SearchService, YamlTranslator]:
    """Get services from singleton client (MCP server compatibility)."""
    client = _get_client()
    yaml_translator = YamlTranslator(os.environ.get("MEMG_YAML_PATH"))
    return client._memory_service, client._search_service, yaml_translator
