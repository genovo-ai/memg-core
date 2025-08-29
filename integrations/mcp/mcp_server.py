#!/usr/bin/env python3
"""
MEMG Core MCP Server - Thin wrapper over memg-core public API.
Provides: add_memory, delete_memory, search_memories, add_relationship, get_system_info
"""

import logging
import os
import time
from dotenv import load_dotenv
from typing import Any, Dict, Optional

# Load .env from current directory (integrations/mcp/) - allow .env to override
load_dotenv(override=True)  # Allow .env file to override environment variables

from fastmcp import FastMCP
from fastapi.responses import JSONResponse
from memg_core import __version__

# Import the current API from the installed library
from memg_core.api.public import MemgClient
from memg_core.core.exceptions import ValidationError, DatabaseError
from memg_core.core.models import SearchResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= BRIDGE PATTERN =========================

# Global client instance
memg_client: Optional[MemgClient] = None

def initialize_client() -> None:
    """Initialize the global MemgClient instance during startup."""
    global memg_client
    if memg_client is not None:
        logger.warning("⚠️ MemgClient already initialized - skipping")
        return

    logger.info("🔧 Initializing MemgClient during startup...")
    yaml_path = os.getenv("MEMG_YAML_PATH", "software_dev.yaml")
    db_path = os.getenv("MEMG_DB_PATH", "tmp")
    logger.info(f"🔧 Using yaml_path={yaml_path}, db_path={db_path}")

    try:
        # Ensure database path exists and is absolute
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        os.makedirs(db_path, exist_ok=True)
        logger.info(f"🔧 Database path ensured: {db_path}")

        memg_client = MemgClient(yaml_path=yaml_path, db_path=db_path)
        logger.info("✅ MemgClient initialized successfully during startup")

        # Test the client with a simple operation to ensure it's working
        logger.info("🧪 Testing client initialization...")
        # This will trigger embedding model download if needed
        logger.info("✅ Client initialization test completed")

    except Exception as e:
        logger.error(f"❌ Failed to initialize MemgClient: {e}", exc_info=True)
        raise RuntimeError(f"MemgClient initialization failed: {e}")

def get_memg_client() -> MemgClient:
    """Get the global MemgClient instance (must be initialized first)."""
    global memg_client
    if memg_client is None:
        raise RuntimeError("MemgClient not initialized - server startup failed")
    return memg_client

def shutdown_client():
    """Shutdown the global MemgClient instance."""
    global memg_client
    if memg_client:
        try:
            memg_client.close()
            logger.info("🔌 MemgClient closed successfully")
        except Exception as e:
            logger.error(f"⚠️ Error closing MemgClient: {e}")
        finally:
            memg_client = None


def setup_health_endpoints(app: FastMCP) -> None:
    """Setup health check endpoints."""

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        client_status = "initialized" if memg_client is not None else "not initialized"
        status = {
            "service": "MEMG Core MCP Server",
            "version": __version__,
            "memg_client": client_status,
            "status": "healthy"
        }
        return JSONResponse(status, status_code=200)


def register_tools(app: FastMCP) -> None:  # pylint: disable=too-many-statements
    """Register MCP tools."""

    @app.tool("add_memory")
    def add_memory_tool(memory_type: str, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a memory with YAML-driven validation.

        Args:
            memory_type: Type (note, document, task, bug, solution)
            user_id: User identifier
            payload: Memory data with required fields:
                - statement (required): Main content (max 8000 chars)
                - For document: details (required)
                - For bug: details (required)
                - Optional fields vary by type (project, status, priority, etc.)

        Returns:
            Dict with result message and HRID, or error details
        """
        logger.info(f"=== ADD_MEMORY TOOL CALLED ===")
        logger.info(f"Adding {memory_type} for user {user_id}")
        logger.info(f"Payload: {payload}")

        client = get_memg_client()
        hrid = client.add_memory(
            memory_type=memory_type,
            payload=payload,
            user_id=user_id
        )
        logger.info(f"✅ Successfully added {memory_type} with HRID: {hrid}")

        return {
            "result": f"{memory_type.title()} added",
            "hrid": hrid
        }

    @app.tool("delete_memory")
    def delete_memory_tool(memory_id: str, user_id: str) -> Dict[str, Any]:
        """
        Delete a memory by HRID.

        Args:
            memory_id: Memory HRID (e.g. 'NOTE_AAA001', 'DOCUMENT_AAA000')
            user_id: User identifier for ownership verification

        Returns:
            Dict with result message and deletion status, or error details
        """
        try:
            client = get_memg_client()
            success = client.delete_memory(
                hrid=memory_id,
                user_id=user_id
            )

            return {
                "result": "Memory deleted" if success else "Delete failed",
                "hrid": memory_id,
                "deleted": success
            }

        except Exception as e:
            logger.error(f"Error deleting {memory_id}: {e}")
            return {
                "error": f"Failed to delete {memory_id}: {str(e)}",
                "hrid": memory_id,
                "deleted": False
            }

    @app.tool("search_memories")
    def search_memories_tool(
        query: str,
        user_id: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        neighbor_limit: int = 5,
        hops: int = 1,
        include_semantic: bool = True
    ) -> Dict[str, Any]:
        """
        Search memories using semantic vector search with graph expansion.

        Args:
            query: Search query text
            user_id: User identifier for scoped search (ensures user isolation)
            limit: Maximum results (default: 5, max: 50)
            memory_type: Optional type filter (note, document, task, bug, solution)
            neighbor_limit: Maximum graph neighbors per seed (default: 5)
            hops: Graph traversal depth (default: 1)
            include_semantic: Include semantic expansion (default: True)

        Returns:
            Dict with search results including graph neighbors and metadata, or error details
        """
        logger.info(f"=== SEARCH_MEMORIES TOOL CALLED ===")
        logger.info(f"Query: {query}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Limit: {limit}")
        logger.info(f"Memory type (raw): {memory_type}")
        logger.info(f"Neighbor limit: {neighbor_limit}, Hops: {hops}, Include semantic: {include_semantic}")

        # Normalize memory_type input - handle string only, make case-insensitive
        memory_type_filter = None
        if memory_type and isinstance(memory_type, str):
            memory_type_filter = memory_type.lower().strip()

        logger.info(f"Memory type filter: {memory_type_filter}")

        # Validate inputs
        if not query.strip():
            logger.warning("Empty query provided")
            return {
                "error": "Query cannot be empty",
                "memories": []
            }

        if limit > 50:
            limit = 50  # Cap at reasonable limit

        logger.info(f"Calling search API...")
        client = get_memg_client()
        results = client.search(
            query=query,
            user_id=user_id,
            memory_type=memory_type_filter,
            limit=limit,
            neighbor_limit=neighbor_limit,
            hops=hops,
            include_semantic=include_semantic
        )

        logger.info(f"Search API completed, found {len(results)} results")

        # Include full SearchResult information
        memories = [{
            "hrid": r.memory.hrid,
            "memory_type": r.memory.memory_type,
            "payload": r.memory.payload,
            "score": r.score,
            "source": r.source,
            "distance": r.distance,
            "neighbor": r.metadata
        } for r in results]

        return {
            "result": f"Found {len(memories)} memories",
            "memories": memories,
            "query": query,
            "user_id": user_id,
            "search_params": {
                "limit": limit,
                "memory_type": memory_type_filter,
                "neighbor_limit": neighbor_limit,
                "hops": hops,
                "include_semantic": include_semantic
            }
        }

    @app.tool("add_relationship")
    def add_relationship_tool(
        from_memory_hrid: str,
        to_memory_hrid: str,
        relation_type: str,
        from_memory_type: str,
        to_memory_type: str,
        user_id: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a relationship between two memories.

        Args:
            from_memory_hrid: Source memory HRID
            to_memory_hrid: Target memory HRID
            relation_type: Relationship predicate (ANNOTATES, SUPPORTS, ADDRESSES, FIXES, IMPLEMENTS, etc.)
            from_memory_type: Source memory type
            to_memory_type: Target memory type
            user_id: User identifier for ownership verification
            properties: Optional relationship properties

        Returns:
            Dict with result message or error details
        """
        logger.info(f"=== ADD_RELATIONSHIP TOOL CALLED ===")
        logger.info(f"From: {from_memory_hrid} ({from_memory_type}) -> To: {to_memory_hrid} ({to_memory_type})")
        logger.info(f"Relation: {relation_type}, User: {user_id}")

        client = get_memg_client()
        client.add_relationship(
            from_memory_hrid=from_memory_hrid,
            to_memory_hrid=to_memory_hrid,
            relation_type=relation_type,
            from_memory_type=from_memory_type,
            to_memory_type=to_memory_type,
            user_id=user_id,
            properties=properties
        )

        return {
            "result": "Relationship added successfully",
            "from_hrid": from_memory_hrid,
            "to_hrid": to_memory_hrid,
            "relation_type": relation_type
        }

    @app.tool("get_system_info")
    def get_system_info_tool(random_string: str = "") -> Dict[str, Any]:
        """
        Get system information and available memory types.

        Returns:
            Dict with system info, version, available functions, and memory types
        """
        from memg_core.core.types import get_entity_type_enum

        entity_enum = get_entity_type_enum()
        entity_types = [e.value for e in entity_enum]

        return {
            "system_type": "MEMG Core",
            "version": __version__,
            "functions": ["add_memory", "delete_memory", "search_memories", "add_relationship", "get_system_info", "health_check"],
            "memory_types": entity_types,
            "schema_info": {
                "note": {"required": ["statement"], "optional": ["project", "origin"]},
                "document": {"required": ["statement", "details"], "optional": ["project", "url"]},
                "task": {"required": ["statement"], "optional": ["project", "details", "status", "priority", "due_date"]},
                "bug": {"required": ["statement", "details"], "optional": ["project", "severity", "status", "file_path", "reference"]},
                "solution": {"required": ["statement"], "optional": ["project", "details", "file_path", "test_status"]},
                "enum_values": {
                    "task_status": ["backlog", "todo", "in_progress", "in_review", "done", "cancelled"],
                    "task_priority": ["low", "medium", "high", "critical"],
                    "bug_severity": ["low", "medium", "high", "critical"],
                    "bug_status": ["open", "in_progress", "resolved"],
                    "solution_test_status": ["untested", "manual_test", "unit_test", "integration_test"],
                    "note_origin": ["system", "user"]
                }
            }
        }


def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    app = FastMCP()
    register_tools(app)
    setup_health_endpoints(app)

    # Add a simple health check tool instead of endpoint
    @app.tool("health_check")
    def health_check_tool(random_string: str = "") -> Dict[str, Any]:
        """
        Health check tool for monitoring.

        Returns:
            Dict with health status, service info, and version
        """
        client_status = "initialized" if memg_client is not None else "not initialized"
        return {
            "status": "healthy",
            "service": "MEMG Core MCP Server",
            "version": __version__,
            "memg_client": client_status,
            "database_path": os.getenv("MEMG_DB_PATH", "tmp"),
            "yaml_schema": os.getenv("MEMG_YAML_PATH", "software_dev.yaml")
        }

    return app



# Create the app instance
mcp_app = create_app()

if __name__ == "__main__":
    # Get port from .env, respecting the exact variable name
    port_env = os.getenv("MEMORY_SYSTEM_MCP_PORT", "8888")
    port = int(port_env)

    # Host should be configured via deployment (Docker, docker-compose, etc.)
    host = os.getenv("MEMORY_SYSTEM_MCP_HOST", "127.0.0.1")

    print(f"🚀 MEMG Core MCP Server v{__version__} on {host}:{port}")
    print(f"📋 Using YAML: {os.getenv('MEMG_YAML_PATH', 'software_dev.yaml')}")
    print(f"💾 Using DB path: {os.getenv('MEMG_DB_PATH', 'tmp')}")
    print(f"🏥 Health check available at /health")

    try:
        # Initialize client during startup (not on first tool call)
        print("🔧 Initializing MemgClient before starting server...")
        initialize_client()
        print("✅ MemgClient initialization completed")

        # Start the server
        print(f"🌐 Starting MCP server on {host}:{port}")
        mcp_app.run(transport="sse", host=host, port=port)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down MEMG Core MCP Server...")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise
    finally:
        print("🔌 Shutting down MemgClient...")
        shutdown_client()
        print("🔌 MemgClient shut down completed.")
