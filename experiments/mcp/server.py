#!/usr/bin/env python3
"""
MEMG Core MCP Server - Production Implementation
Clean, efficient server with singleton client management and FastMCP compatibility.
"""

import logging
import os
from typing import Any, Dict, Optional
from pydantic import Field

from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from memg_core import __version__
from memg_core.api.public import MemgClient
from memg_core.core.yaml_translator import YamlTranslator

# Load environment variables
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= GLOBAL CLIENT SINGLETON =========================

# Global instances - initialized once at module level
_client: Optional[MemgClient] = None
_yaml_translator: Optional[YamlTranslator] = None

def _initialize_client() -> None:
    """Initialize the global MemgClient and YamlTranslator singletons."""
    global _client, _yaml_translator

    if _client is not None:
        logger.info("Client already initialized, skipping")
        return

    # Get configuration from environment
    yaml_path = os.getenv("MEMG_YAML_SCHEMA")
    db_path = os.getenv("MEMG_DB_PATH")

    if not yaml_path:
        raise RuntimeError("MEMG_YAML_SCHEMA environment variable is required")
    if not db_path:
        raise RuntimeError("MEMG_DB_PATH environment variable is required")

    logger.info(f"Initializing MemgClient: yaml={yaml_path}, db={db_path}")

    try:
        # Ensure database path exists
        os.makedirs(db_path, exist_ok=True)

        # Initialize client and YAML translator
        _client = MemgClient(yaml_path=yaml_path, db_path=db_path)
        _yaml_translator = YamlTranslator(yaml_path)

        logger.info("✅ MemgClient and YamlTranslator initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize client: {e}", exc_info=True)
        raise RuntimeError(f"Client initialization failed: {e}")

def get_client() -> MemgClient:
    """Get the global MemgClient singleton."""
    if _client is None:
        raise RuntimeError("Client not initialized - call _initialize_client() first")
    return _client

def get_yaml_translator() -> YamlTranslator:
    """Get the global YamlTranslator singleton."""
    if _yaml_translator is None:
        raise RuntimeError("YamlTranslator not initialized - call _initialize_client() first")
    return _yaml_translator

def close_client() -> None:
    """Close the global client singleton."""
    global _client, _yaml_translator
    if _client:
        try:
            _client.close()
            logger.info("✅ Client closed successfully")
        except Exception as e:
            logger.error(f"⚠️ Error closing client: {e}")
        finally:
            _client = None
            _yaml_translator = None

# ========================= TOOL REGISTRATION =========================

def register_search_tools(app: FastMCP) -> None:
    """Register search-related tools."""

    @app.tool("search_memories", description="Search memories using semantic vector search with graph expansion.")
    def search_memories(
        query: str = Field(..., description="Search query text"),
        user_id: str = Field(..., description="User identifier (required for data isolation)"),
        limit: int = Field(5, description="Maximum results (default: 5, max: 50)"),
        memory_type: Optional[str] = Field(None, description="Filter by memory type (optional)"),
        neighbor_limit: int = Field(5, description="Max graph neighbors per result (default: 5)"),
        hops: int = Field(1, description="Graph traversal depth (default: 1)"),
        score_threshold: Optional[float] = Field(None, description="Minimum similarity score threshold (0.0-1.0)"),
        decay_rate: Optional[float] = Field(None, description="Score decay factor per hop (1.0 = no decay)"),
        decay_threshold: Optional[float] = Field(None, description="Explicit neighbor score threshold")
    ) -> Dict[str, Any]:
        """Search memories - direct API call."""

        logger.info(f"SEARCH: query='{query}', user_id='{user_id}', limit={limit}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required", "memories": []}
        if not query or not query.strip():
            return {"error": "query cannot be empty", "memories": []}

        # Limit protection
        limit = min(limit, 50)

        try:
            client = get_client()
            result = client.search(
                query=query.strip(),
                user_id=user_id.strip(),
                memory_type=memory_type.lower().strip() if memory_type else None,
                limit=limit,
                neighbor_limit=neighbor_limit,
                hops=hops,
                score_threshold=score_threshold,
                decay_rate=decay_rate,
                decay_threshold=decay_threshold
            )

            logger.info(f"Search result: {len(result.memories)} memories, {len(result.neighbors)} neighbors")

            # Convert to JSON-serializable format
            result_dict = result.model_dump(mode='json')

            return {
                "status": f"Found {len(result.memories)} memories and {len(result.neighbors)} neighbors",
                "memories": result_dict.get("memories", []),
                "neighbors": result_dict.get("neighbors", []),
                "query": query,
                "user_id": user_id
            }

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return {
                "error": f"Search failed: {str(e)}",
                "memories": [],
                "query": query,
                "user_id": user_id
            }

def register_get_tools(app: FastMCP) -> None:
    """Register get-related tools."""

    @app.tool("get_memory_by_hrid", description="Get a single memory by HRID with optional neighbor expansion.")
    def get_memory_by_hrid(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)"),
        include_neighbors: bool = Field(False, description="Include graph neighbors (default: false)"),
        hops: int = Field(1, description="Graph traversal depth when include_neighbors=true (default: 1)"),
        neighbor_limit: int = Field(5, description="Maximum neighbors to return per hop (default: 5)"),
        relation_types: Optional[list[str]] = Field(None, description="Filter by specific relationship types")
    ) -> Dict[str, Any]:
        """Get memory by HRID - direct API call."""

        logger.info(f"GET_MEMORY: hrid='{hrid}', user_id='{user_id}', include_neighbors={include_neighbors}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required"}
        if not hrid or not hrid.strip():
            return {"error": "hrid is required"}

        try:
            client = get_client()
            result = client.get_memory(
                hrid=hrid.strip(),
                user_id=user_id.strip(),
                memory_type=memory_type,
                include_neighbors=include_neighbors,
                hops=hops,
                relation_types=relation_types,
                neighbor_limit=neighbor_limit
            )

            if result is None:
                return {
                    "result": "Memory not found",
                    "hrid": hrid,
                    "memory": None
                }

            # Convert to JSON-serializable format
            result_dict = result.model_dump(mode='json')
            memories = result_dict.get("memories", [])
            neighbors = result_dict.get("neighbors", [])

            if not memories:
                return {
                    "result": "Memory not found",
                    "hrid": hrid,
                    "memory": None
                }

            response = {
                "result": "Memory retrieved successfully",
                "memory": memories[0]  # Single memory
            }

            if neighbors:
                response["neighbors"] = neighbors
                response["neighbor_count"] = len(neighbors)

            return response

        except Exception as e:
            logger.error(f"Get memory failed: {e}", exc_info=True)
            return {
                "error": f"Get memory failed: {str(e)}",
                "hrid": hrid,
                "memory": None
            }

    @app.tool("list_memories_by_type", description="List multiple memories with filtering and optional graph expansion.")
    def list_memories_by_type(
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description="Filter by memory type (optional)"),
        limit: int = Field(50, description="Maximum results (default: 50)"),
        offset: int = Field(0, description="Skip first N results for pagination (default: 0)"),
        include_neighbors: bool = Field(False, description="Include graph neighbors (default: false)"),
        hops: int = Field(1, description="Graph traversal depth when include_neighbors=true (default: 1)"),
        filters: Optional[Dict[str, Any]] = Field(None, description="Additional field-based filters (optional)")
    ) -> Dict[str, Any]:
        """List memories by type - direct API call."""

        logger.info(f"LIST_MEMORIES: user_id='{user_id}', memory_type='{memory_type}', limit={limit}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required", "memories": []}

        try:
            client = get_client()
            result = client.get_memories(
                user_id=user_id.strip(),
                memory_type=memory_type,
                filters=filters,
                limit=limit,
                offset=offset,
                include_neighbors=include_neighbors,
                hops=hops
            )

            # Convert to JSON-serializable format
            result_dict = result.model_dump(mode='json')
            memories = result_dict.get("memories", [])
            neighbors = result_dict.get("neighbors", [])

            response = {
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

            if neighbors:
                response["neighbors"] = neighbors
                response["neighbor_count"] = len(neighbors)

            return response

        except Exception as e:
            logger.error(f"List memories failed: {e}", exc_info=True)
            return {
                "error": f"List memories failed: {str(e)}",
                "memories": [],
                "user_id": user_id
            }

def register_add_tools(app: FastMCP) -> None:
    """Register dynamic add_* tools for each memory type."""

    try:
        yaml_translator = get_yaml_translator()
        entity_types = yaml_translator.get_entity_types()

        # Skip memo - it's a base type for inheritance only
        filtered_types = [t for t in entity_types if t != "memo"]
        logger.info(f"Registering add tools for types: {filtered_types}")

        for memory_type in filtered_types:
            _register_add_tool(app, memory_type, yaml_translator)

    except Exception as e:
        logger.error(f"Failed to register add tools: {e}", exc_info=True)
        raise

def _register_add_tool(app: FastMCP, memory_type: str, yaml_translator: YamlTranslator) -> None:
    """Register a single add_* tool for a memory type."""

    tool_name = f"add_{memory_type}"

    # Get description from YAML
    try:
        entities_map = yaml_translator._entities_map()
        entity_spec = entities_map.get(memory_type.lower())
        description = f"Add a {memory_type}"
        if entity_spec and "description" in entity_spec:
            description = f"Add a {memory_type}: {entity_spec['description']}"
    except Exception:
        description = f"Add a {memory_type} memory"

    @app.tool(tool_name, description=description)
    def add_tool(
        user_id: str = Field(..., description="User identifier - separates user's memories from each other"),
        data: Dict[str, Any] = Field(..., description=f"Data fields for {memory_type}")
    ) -> Dict[str, Any]:
        """Add memory - direct API call."""

        logger.info(f"ADD_{memory_type.upper()}: user_id='{user_id}', data={data}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {
                "error": "user_id is required",
                "memory_type": memory_type
            }

        try:
            client = get_client()
            hrid = client.add_memory(
                memory_type=memory_type,
                payload=data,
                user_id=user_id.strip()
            )

            logger.info(f"Successfully added {memory_type} with HRID: {hrid}")

            return {
                "result": f"{memory_type.title()} added successfully",
                "hrid": hrid,
                "memory_type": memory_type
            }

        except Exception as e:
            logger.error(f"Add {memory_type} failed: {e}", exc_info=True)
            return {
                "error": f"Failed to add {memory_type}: {str(e)}",
                "memory_type": memory_type,
                "user_id": user_id
            }

def register_other_tools(app: FastMCP) -> None:
    """Register other tools (delete, update, relationships, system info)."""

    @app.tool("delete_memory", description="Delete a memory by HRID.")
    def delete_memory(
        memory_id: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)")
    ) -> Dict[str, Any]:
        """Delete memory - direct API call."""

        logger.info(f"DELETE_MEMORY: hrid='{memory_id}', user_id='{user_id}'")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required"}
        if not memory_id or not memory_id.strip():
            return {"error": "memory_id is required"}

        try:
            client = get_client()
            success = client.delete_memory(
                hrid=memory_id.strip(),
                user_id=user_id.strip()
            )

            return {
                "result": "Memory deleted" if success else "Delete failed",
                "hrid": memory_id,
                "deleted": success
            }

        except Exception as e:
            logger.error(f"Delete memory failed: {e}", exc_info=True)
            return {
                "error": f"Failed to delete memory: {str(e)}",
                "hrid": memory_id
            }

    @app.tool("update_memory", description="Update memory with partial payload changes (patch-style update).")
    def update_memory(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        payload_updates: Dict[str, Any] = Field(..., description="Payload updates (only fields you want to change)"),
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)")
    ) -> Dict[str, Any]:
        """Update memory - direct API call."""

        logger.info(f"UPDATE_MEMORY: hrid='{hrid}', user_id='{user_id}', updates={payload_updates}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required"}
        if not hrid or not hrid.strip():
            return {"error": "hrid is required"}
        if not payload_updates:
            return {"error": "payload_updates cannot be empty"}

        try:
            client = get_client()
            success = client.update_memory(
                hrid=hrid.strip(),
                payload_updates=payload_updates,
                user_id=user_id.strip(),
                memory_type=memory_type
            )

            return {
                "result": "Memory updated successfully" if success else "Update failed",
                "hrid": hrid,
                "updated": success
            }

        except Exception as e:
            logger.error(f"Update memory failed: {e}", exc_info=True)
            return {
                "error": f"Failed to update memory: {str(e)}",
                "hrid": hrid
            }

    @app.tool("add_relationship", description="Add a relationship between two memories.")
    def add_relationship(
        from_memory_hrid: str = Field(..., description="Source memory HRID"),
        to_memory_hrid: str = Field(..., description="Target memory HRID"),
        relation_type: str = Field(..., description="Relationship type"),
        from_memory_type: str = Field(..., description="Source entity type"),
        to_memory_type: str = Field(..., description="Target entity type"),
        user_id: str = Field(..., description="User identifier"),
        properties: Optional[Dict[str, Any]] = Field(None, description="Additional relationship properties (optional)")
    ) -> Dict[str, Any]:
        """Add relationship - direct API call."""

        logger.info(f"ADD_RELATIONSHIP: {from_memory_hrid} -[{relation_type}]-> {to_memory_hrid}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required"}

        required_fields = [from_memory_hrid, to_memory_hrid, relation_type, from_memory_type, to_memory_type]
        if not all(field and field.strip() for field in required_fields):
            return {"error": "All relationship fields are required"}

        try:
            client = get_client()
            client.add_relationship(
                from_memory_hrid=from_memory_hrid.strip(),
                to_memory_hrid=to_memory_hrid.strip(),
                relation_type=relation_type.strip(),
                from_memory_type=from_memory_type.strip(),
                to_memory_type=to_memory_type.strip(),
                user_id=user_id.strip(),
                properties=properties
            )

            return {
                "result": "Relationship added successfully",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type
            }

        except Exception as e:
            logger.error(f"Add relationship failed: {e}", exc_info=True)
            return {
                "error": f"Failed to add relationship: {str(e)}",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type
            }

    @app.tool("delete_relationship", description="Delete a relationship between two memories.")
    def delete_relationship(
        from_memory_hrid: str = Field(..., description="Source memory HRID"),
        to_memory_hrid: str = Field(..., description="Target memory HRID"),
        relation_type: str = Field(..., description="Relationship type"),
        user_id: str = Field(..., description="User identifier"),
        from_memory_type: Optional[str] = Field(None, description="Source entity type (optional)"),
        to_memory_type: Optional[str] = Field(None, description="Target entity type (optional)")
    ) -> Dict[str, Any]:
        """Delete relationship - direct API call."""

        logger.info(f"DELETE_RELATIONSHIP: {from_memory_hrid} -[{relation_type}]-> {to_memory_hrid}")

        # Basic validation
        if not user_id or not user_id.strip():
            return {"error": "user_id is required"}

        required_fields = [from_memory_hrid, to_memory_hrid, relation_type]
        if not all(field and field.strip() for field in required_fields):
            return {"error": "from_memory_hrid, to_memory_hrid, and relation_type are required"}

        try:
            client = get_client()
            success = client.delete_relationship(
                from_memory_hrid=from_memory_hrid.strip(),
                to_memory_hrid=to_memory_hrid.strip(),
                relation_type=relation_type.strip(),
                from_memory_type=from_memory_type.strip() if from_memory_type else None,
                to_memory_type=to_memory_type.strip() if to_memory_type else None,
                user_id=user_id.strip()
            )

            return {
                "result": "Relationship deleted successfully" if success else "Relationship not found",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type,
                "deleted": success
            }

        except Exception as e:
            logger.error(f"Delete relationship failed: {e}", exc_info=True)
            return {
                "error": f"Failed to delete relationship: {str(e)}",
                "from_hrid": from_memory_hrid,
                "to_hrid": to_memory_hrid,
                "relation_type": relation_type
            }

    @app.tool("get_system_info", description="Get system information and available tools.")
    def get_system_info(random_string: str = "") -> Dict[str, Any]:
        """Get system info."""

        try:
            from memg_core.core.types import get_entity_type_enum

            entity_enum = get_entity_type_enum()
            entity_types = [e.value for e in entity_enum]

            yaml_schema = os.getenv("MEMG_YAML_SCHEMA", "not configured")

            return {
                "system_type": "MEMG Core (Production)",
                "version": __version__,
                "functions": [
                    "search_memories", "get_memory_by_hrid", "list_memories_by_type",
                    "delete_memory", "update_memory", "add_relationship", "delete_relationship",
                    "get_system_info"
                ] + [f"add_{t}" for t in entity_types if t != "memo"],
                "memory_types": entity_types,
                "yaml_schema": yaml_schema,
                "note": "Production server with singleton client management"
            }

        except Exception as e:
            logger.error(f"Get system info failed: {e}", exc_info=True)
            return {
                "system_type": "MEMG Core (Production)",
                "version": __version__,
                "error": f"Failed to get schema info: {str(e)}",
                "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured")
            }

# ========================= APP CREATION =========================

def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""

    # Initialize client singleton ONCE at app creation
    _initialize_client()

    app = FastMCP()

    # Register all tools
    try:
        register_search_tools(app)
        register_get_tools(app)
        register_add_tools(app)
        register_other_tools(app)
        logger.info("✅ All tools registered successfully")
    except Exception as e:
        logger.error(f"❌ Failed to register tools: {e}")
        raise

    # Health endpoint for Docker
    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        return JSONResponse({
            "service": "MEMG Core MCP Server (Production)",
            "version": __version__,
            "status": "healthy",
            "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured"),
            "db_path": os.getenv("MEMG_DB_PATH", "not configured")
        }, status_code=200)

    return app

# ========================= FASTMCP EXPORT =========================

# Create the app instance for FastMCP to run
mcp_app = create_app()
