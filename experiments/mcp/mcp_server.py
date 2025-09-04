#!/usr/bin/env python3
"""
MEMG Core MCP Server - Generic wrapper over memg-core public API.
Provides: add_memory, delete_memory, search_memories, add_relationship, get_system_info

This is a generic MCP server that expects:
- MEMG_YAML_SCHEMA environment variable pointing to the YAML schema file
- Proper database paths configured via environment variables
"""

import logging
import os
import time
from typing import Any, Dict, Optional
from pydantic import Field

from dotenv import load_dotenv

# Load .env from current directory - allow .env to override
load_dotenv(override=True)  # Allow .env file to override environment variables

from fastapi.responses import JSONResponse
from fastmcp import FastMCP
# Use YamlTranslator directly - no need for separate docstring helper
from memg_core.core.yaml_translator import YamlTranslator

from memg_core import __version__
# Import the current API from the installed library
from memg_core.api.public import MemgClient

# from memg_core.core.exceptions import ValidationError, DatabaseError
# from memg_core.core.models import SearchResult


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= BRIDGE PATTERN =========================

# Global client instance
memg_client: Optional[MemgClient] = None

# Global YAML translator instance
yaml_translator: Optional[YamlTranslator] = None

def initialize_client() -> None:
    """Initialize the global MemgClient instance and YAML translator during startup."""
    global memg_client, yaml_translator
    if memg_client is not None:
        logger.warning("⚠️ MemgClient already initialized - skipping")
        return

    logger.info("🔧 Initializing MemgClient and YAML translator during startup...")

    # Get YAML schema from environment - this is required for generic server
    yaml_path = os.getenv("MEMG_YAML_SCHEMA")
    if not yaml_path:
        raise RuntimeError("MEMG_YAML_SCHEMA environment variable is required for generic MCP server")

    logger.info(f"📋 Using YAML schema: {yaml_path}")

    # Check if we have mounted volumes configured
    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH")

    if qdrant_path and kuzu_path:
        # Using mounted volumes - create a temporary structure that memg-core expects
        # memg-core expects db_path/qdrant and db_path/kuzu structure
        db_path = "/app/data"  # Use a consistent path
        os.makedirs(f"{db_path}/qdrant", exist_ok=True)
        os.makedirs(f"{db_path}/kuzu", exist_ok=True)

        # Create symlinks to the mounted volumes
        qdrant_link = f"{db_path}/qdrant"
        kuzu_link = f"{db_path}/kuzu"

        # Remove existing directories and create symlinks
        if os.path.exists(qdrant_link) and not os.path.islink(qdrant_link):
            os.rmdir(qdrant_link)
        if not os.path.exists(qdrant_link):
            os.symlink(qdrant_path, qdrant_link)

        if os.path.exists(kuzu_link) and not os.path.islink(kuzu_link):
            os.rmdir(kuzu_link)
        if not os.path.exists(kuzu_link):
            os.symlink(os.path.dirname(kuzu_path), kuzu_link)  # kuzu_path includes db name

        logger.info(f"🔧 Using mounted volumes via symlinks - qdrant: {qdrant_path} -> {qdrant_link}, kuzu: {kuzu_path} -> {kuzu_link}")
    else:
        # Fallback to tmp directory for non-mounted usage
        db_path = "tmp"
        logger.info(f"🔧 Using internal storage: {db_path}")

    logger.info(f"🔧 Using yaml_path={yaml_path}, db_path={db_path}")

    try:
        # Ensure database path exists and is absolute
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        os.makedirs(db_path, exist_ok=True)
        logger.info(f"🔧 Database path ensured: {db_path}")

        memg_client = MemgClient(yaml_path=yaml_path, db_path=db_path)
        logger.info("✅ MemgClient initialized successfully during startup")

        # Initialize YAML translator with the same YAML path
        try:
            yaml_translator = YamlTranslator(yaml_path)
            logger.info("✅ YAML translator initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize YAML translator: {e}")
            logger.warning("⚠️ Will use fallback docstrings")
            yaml_translator = None

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

def get_memory_types_for_field() -> str:
    """Get memory types string for Field descriptions."""
    global yaml_translator

    try:
        if yaml_translator:
            entities = yaml_translator.get_entity_types()
            return ", ".join(sorted(entities))
    except Exception:
        pass

    return "bug, document, memo, note, solution, task"  # fallback

def get_dynamic_docstring(tool_name: str) -> str:
    """Generate docstrings from templates with YAML values."""
    global yaml_translator

    # Simple docstring templates
    templates = {
        "add_memory": "Add a memory with proper payload based on the type of memory.",
        "delete_memory": "Delete a memory by HRID.",
        "update_memory": "Update memory with partial payload changes (patch-style update).",
        "search_memories": "Search memories using semantic vector search with graph expansion.",
        "get_memory": "Get a single memory by HRID.",
        "get_memories": "Get multiple memories with filtering and optional graph expansion.",
        "add_relationship": "Add a relationship between two memories.",
        "delete_relationship": "Delete a relationship between two memories."
    }

    return templates.get(tool_name, f"Tool: {tool_name}")

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
            "service": "MEMG Core MCP Server (Generic)",
            "version": __version__,
            "memg_client": client_status,
            "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured"),
            "status": "healthy"
        }
        return JSONResponse(status, status_code=200)


def register_tools(app: FastMCP) -> None:  # pylint: disable=too-many-statements
    """Register MCP tools."""

    @app.tool("add_memory", description=get_dynamic_docstring("add_memory"))
    def add_memory_tool(
        memory_type: str = Field(..., description=f"One of the supported memory types: {get_memory_types_for_field()}"),
        user_id: str = Field(..., description="User identifier - separates user's memories from each other"),
        payload: Dict[str, Any] = Field(..., description="Memory data with required fields based on the type of memory")
    ) -> Dict[str, Any]:
        logger.info(f"=== ADD_MEMORY TOOL CALLED ===")
        logger.info(f"Adding {memory_type} for user {user_id}")
        logger.info(f"Payload: {payload}")

        try:
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

        except Exception as e:
            logger.error(f"❌ Error adding {memory_type}: {e}")
            return {
                "error": f"Failed to add {memory_type}: {str(e)}",
                "memory_type": memory_type,
                "user_id": user_id
            }


    @app.tool("delete_memory", description=get_dynamic_docstring("delete_memory"))
    def delete_memory_tool(
        memory_id: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)")
    ) -> Dict[str, Any]:
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


    @app.tool("update_memory", description=get_dynamic_docstring("update_memory"))
    def update_memory_tool(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        payload_updates: Dict[str, Any] = Field(..., description="Payload updates (only fields you want to change)"),
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== UPDATE_MEMORY TOOL CALLED ===")
        logger.info(f"Updating {hrid} for user {user_id}")
        logger.info(f"Updates: {payload_updates}")

        try:
            client = get_memg_client()
            success = client.update_memory(
                hrid=hrid,
                payload_updates=payload_updates,
                user_id=user_id,
                memory_type=memory_type
            )

            if success:
                logger.info(f"✅ Successfully updated {hrid}")
                return {
                    "result": "Memory updated successfully",
                    "hrid": hrid,
                    "updated": True
                }
            else:
                logger.warning(f"⚠️ Update failed for {hrid}")
                return {
                    "result": "Update failed",
                    "hrid": hrid,
                    "updated": False
                }

        except Exception as e:
            logger.error(f"Error updating {hrid}: {e}")
            return {
                "error": f"Failed to update {hrid}: {str(e)}",
                "hrid": hrid,
                "updated": False
            }


    @app.tool("search_memories", description=get_dynamic_docstring("search_memories"))
    def search_memories_tool(
        query: str = Field(..., description="Search query text"),
        user_id: str = Field(..., description="User identifier (required for data isolation)"),
        limit: int = Field(5, description="Maximum results (default: 5, max: 50)"),
        memory_type: Optional[str] = Field(None, description=f"Filter by type ({get_memory_types_for_field()}, optional)"),
        neighbor_limit: int = Field(5, description="Max graph neighbors per result (default: 5)"),
        hops: int = Field(1, description="Graph traversal depth (default: 1)"),
        include_semantic: bool = Field(True, description="Include semantic search (default: true)")
    ) -> Dict[str, Any]:
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

        logger.info(f"Search API completed, found {len(results.memories)} seeds and {len(results.neighbors)} neighbors")

        # Convert new SearchResult format to MCP response
        memories = []

        # Add seed memories (full payloads with scores and relationships)
        for seed in results.memories:
            memories.append({
                "hrid": seed.hrid,
                "memory_type": seed.memory_type,
                "payload": seed.payload,
                "score": seed.score,
                "source": "seed",
                "relationships": seed.relationships
            })

        # Add neighbor memories (anchor-only payloads)
        for neighbor in results.neighbors:
            memories.append({
                "hrid": neighbor.hrid,
                "memory_type": neighbor.memory_type,
                "payload": neighbor.payload,
                "score": None,  # Neighbors don't have direct scores
                "source": "neighbor",
                "relationships": []
            })

        return {
            "result": f"Found {len(results.memories)} seeds and {len(results.neighbors)} neighbors ({len(memories)} total)",
            "memories": memories,
            "seeds_count": len(results.memories),
            "neighbors_count": len(results.neighbors),
            "total_count": len(memories),
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


    @app.tool("add_relationship", description=get_dynamic_docstring("add_relationship"))
    def add_relationship_tool(
        from_memory_hrid: str = Field(..., description="Source memory HRID"),
        to_memory_hrid: str = Field(..., description="Target memory HRID"),
        relation_type: str = Field(..., description="Relationship type"),
        from_memory_type: str = Field(..., description="Source entity type"),
        to_memory_type: str = Field(..., description="Target entity type"),
        user_id: str = Field(..., description="User identifier"),
        properties: Optional[Dict[str, Any]] = Field(None, description="Additional relationship properties (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== ADD_RELATIONSHIP TOOL CALLED ===")
        logger.info(f"From: {from_memory_hrid} ({from_memory_type}) -> To: {to_memory_hrid} ({to_memory_type})")
        logger.info(f"Relation: {relation_type}, User: {user_id}")

        try:
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

        except Exception as e:
            logger.error(f"❌ Error adding relationship: {e}")
            return {
                "error": f"Failed to add relationship: {str(e)}",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type
            }


    @app.tool("delete_relationship", description=get_dynamic_docstring("delete_relationship"))
    def delete_relationship_tool(
        from_memory_hrid: str,
        to_memory_hrid: str,
        relation_type: str,
        user_id: str,
        from_memory_type: Optional[str] = None,
        to_memory_type: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"=== DELETE_RELATIONSHIP TOOL CALLED ===")
        logger.info(f"Deleting: {from_memory_hrid} -[{relation_type}]-> {to_memory_hrid}")
        logger.info(f"User: {user_id}")

        try:
            client = get_memg_client()
            success = client.delete_relationship(
                from_memory_hrid=from_memory_hrid,
                to_memory_hrid=to_memory_hrid,
                relation_type=relation_type,
                from_memory_type=from_memory_type,
                to_memory_type=to_memory_type,
                user_id=user_id
            )

            if success:
                logger.info(f"✅ Successfully deleted relationship")
                return {
                    "result": "Relationship deleted successfully",
                    "from_hrid": from_memory_hrid,
                    "to_hrid": to_memory_hrid,
                    "relation_type": relation_type,
                    "deleted": True
                }
            else:
                logger.warning(f"⚠️ Relationship not found or delete failed")
                return {
                    "result": "Relationship not found",
                    "from_hrid": from_memory_hrid,
                    "to_hrid": to_memory_hrid,
                    "relation_type": relation_type,
                    "deleted": False
                }

        except Exception as e:
            logger.error(f"Error deleting relationship: {e}")
            return {
                "error": f"Failed to delete relationship: {str(e)}",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type,
                "deleted": False
            }


    @app.tool("get_system_info")
    def get_system_info_tool(random_string: str = "") -> Dict[str, Any]:
        try:
            from memg_core.core.types import get_entity_type_enum

            entity_enum = get_entity_type_enum()
            entity_types = [e.value for e in entity_enum]

            # Get YAML schema info
            yaml_schema = os.getenv("MEMG_YAML_SCHEMA", "not configured")

            return {
                "system_type": "MEMG Core (Generic)",
                "version": __version__,
                "functions": ["add_memory", "delete_memory", "update_memory", "search_memories", "get_memory", "get_memories", "add_relationship", "delete_relationship", "get_system_info", "health_check"],
                "memory_types": entity_types,
                "yaml_schema": yaml_schema,
                "note": "Schema details depend on the loaded YAML configuration"
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {
                "system_type": "MEMG Core (Generic)",
                "version": __version__,
                "error": f"Failed to get schema info: {str(e)}",
                "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured")
            }

    @app.tool("get_memory", description=get_dynamic_docstring("get_memory"))
    def get_memory_tool(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== GET_MEMORY TOOL CALLED ===")
        logger.info(f"Getting memory {hrid} for user {user_id}")

        try:
            client = get_memg_client()
            memory_data = client.get_memory(
                hrid=hrid,
                user_id=user_id,
                memory_type=memory_type
            )

            if memory_data:
                logger.info(f"✅ Successfully retrieved {hrid}")
                return {
                    "result": "Memory retrieved successfully",
                    "memory": memory_data
                }
            else:
                logger.warning(f"⚠️ Memory not found: {hrid}")
                return {
                    "result": "Memory not found",
                    "hrid": hrid,
                    "memory": None
                }

        except Exception as e:
            logger.error(f"Error retrieving {hrid}: {e}")
            return {
                "error": f"Failed to retrieve {hrid}: {str(e)}",
                "hrid": hrid,
                "memory": None
            }

    @app.tool("get_memories", description=get_dynamic_docstring("get_memories"))
    def get_memories_tool(
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description=f"Filter by type ({get_memory_types_for_field()}, optional)"),
        limit: int = Field(50, description="Maximum results (default: 50)"),
        offset: int = Field(0, description="Skip first N results for pagination (default: 0)"),
        include_neighbors: bool = Field(False, description="Include graph neighbors (default: false)"),
        hops: int = Field(1, description="Graph traversal depth when include_neighbors=true (default: 1)"),
        filters: Optional[Dict[str, Any]] = Field(None, description="Additional field-based filters (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== GET_MEMORIES TOOL CALLED ===")
        logger.info(f"Getting memories for user {user_id}, type: {memory_type}, limit: {limit}")

        try:
            client = get_memg_client()
            memories = client.get_memories(
                user_id=user_id,
                memory_type=memory_type,
                filters=filters,
                limit=limit,
                offset=offset,
                include_neighbors=include_neighbors,
                hops=hops
            )

            logger.info(f"✅ Successfully retrieved {len(memories)} memories")
            return {
                "result": f"Retrieved {len(memories)} memories",
                "memories": memories,
                "count": len(memories),
                "query_params": {
                    "memory_type": memory_type,
                    "limit": limit,
                    "offset": offset,
                    "include_neighbors": include_neighbors,
                    "filters": filters
                }
            }

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return {
                "error": f"Failed to retrieve memories: {str(e)}",
                "memories": [],
                "count": 0
            }

def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    # Initialize client and docstring helper BEFORE registering tools
    # This ensures dynamic docstrings are available when decorators run
    initialize_client()

    app = FastMCP()
    register_tools(app)
    setup_health_endpoints(app)

    # Add a simple health check tool instead of endpoint
    @app.tool("health_check")
    def health_check_tool(random_string: str = "") -> Dict[str, Any]:
        client_status = "initialized" if memg_client is not None else "not initialized"
        return {
            "status": "healthy",
            "service": "MEMG Core MCP Server (Generic)",
            "version": __version__,
            "memg_client": client_status,
            "database_path": os.getenv("QDRANT_STORAGE_PATH", "tmp") if os.getenv("QDRANT_STORAGE_PATH") else "tmp",
            "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured"),
            "storage_type": "mounted_volumes" if os.getenv("QDRANT_STORAGE_PATH") else "internal"
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

    print(f"🚀 MEMG Core MCP Server (Generic) v{__version__} on {host}:{port}")
    print(f"📋 Using YAML: {os.getenv('MEMG_YAML_SCHEMA', 'NOT CONFIGURED - REQUIRED!')}")
    print(f"💾 Using DB path: {os.getenv('QDRANT_STORAGE_PATH', 'tmp')}")
    print(f"🏥 Health check available at /health")

    try:
        # Client is already initialized in create_app()
        print("✅ MemgClient initialization completed during app creation")

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
