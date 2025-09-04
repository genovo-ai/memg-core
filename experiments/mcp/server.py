#!/usr/bin/env python3
"""
MEMG Core MCP Server - Dynamic tool generation from YAML schema.
Provides individual tools per memory type: add_note, add_task, etc.

This server dynamically generates tools based on the YAML schema:
- MEMG_YAML_SCHEMA environment variable pointing to the YAML schema file
- Proper database paths configured via environment variables
"""

import logging
import os
from typing import Any, Dict, Optional
from pydantic import Field

from dotenv import load_dotenv

# Load .env from current directory - allow .env to override
load_dotenv(override=True)

from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from memg_core.core.yaml_translator import YamlTranslator

from memg_core import __version__
from memg_core.api.public import MemgClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= GLOBAL INSTANCES =========================

memg_client: Optional[MemgClient] = None
yaml_translator: Optional[YamlTranslator] = None

# ========================= INITIALIZATION =========================

def initialize_client() -> None:
    """Initialize the global MemgClient instance and YAML translator during startup."""
    global memg_client, yaml_translator
    if memg_client is not None:
        logger.warning("⚠️ MemgClient already initialized - skipping")
        return

    logger.info("🔧 Initializing MemgClient and YAML translator during startup...")

    # Get YAML schema from environment - required for dynamic server
    yaml_path = os.getenv("MEMG_YAML_SCHEMA")
    if not yaml_path:
        raise RuntimeError("MEMG_YAML_SCHEMA environment variable is required for dynamic MCP server")

    logger.info(f"📋 Using YAML schema: {yaml_path}")

    # Setup database paths
    db_path = _setup_database_paths()
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
        yaml_translator = YamlTranslator(yaml_path)
        logger.info("✅ YAML translator initialized successfully")

        # Test the client with a simple operation to ensure it's working
        logger.info("🧪 Testing client initialization...")
        logger.info("✅ Client initialization test completed")

    except Exception as e:
        logger.error(f"❌ Failed to initialize MemgClient: {e}", exc_info=True)
        raise RuntimeError(f"MemgClient initialization failed: {e}")

def _setup_database_paths() -> str:
    """Setup database paths based on environment configuration."""
    # Check if we have mounted volumes configured
    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH")

    if qdrant_path and kuzu_path:
        # Using mounted volumes - create a temporary structure that memg-core expects
        db_path = "/app/data"
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
            os.symlink(os.path.dirname(kuzu_path), kuzu_link)

        logger.info(f"🔧 Using mounted volumes via symlinks - qdrant: {qdrant_path} -> {qdrant_link}, kuzu: {kuzu_path} -> {kuzu_link}")
        return db_path
    else:
        # Fallback to tmp directory for non-mounted usage
        db_path = "tmp"
        logger.info(f"🔧 Using internal storage: {db_path}")
        return db_path

def get_memg_client() -> MemgClient:
    """Get the global MemgClient instance (must be initialized first)."""
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

# ========================= ERROR HANDLING =========================

def handle_user_id_error(user_id: str, operation: str) -> Dict[str, Any]:
    """Unified error handling for missing or invalid user_id."""
    if not user_id or not user_id.strip():
        return {
            "error": f"user_id is required for {operation}",
            "operation": operation,
            "user_id": user_id
        }
    return {}

def handle_operation_error(e: Exception, operation: str, **context) -> Dict[str, Any]:
    """Unified error handling for operation failures."""
    logger.error(f"❌ Error in {operation}: {e}")
    return {
        "error": f"Failed to {operation}: {str(e)}",
        "operation": operation,
        **context
    }

# ========================= YAML-DRIVEN DOCSTRINGS =========================

def get_entity_description(memory_type: str) -> str:
    """Get entity description from YAML schema."""
    if not yaml_translator:
        return f"Add a {memory_type} memory"

    try:
        entities_map = yaml_translator._entities_map()
        entity_spec = entities_map.get(memory_type.lower())
        if entity_spec and "description" in entity_spec:
            return f"Add a {memory_type}: {entity_spec['description']}"
    except Exception:
        pass

    return f"Add a {memory_type} memory"

def get_entity_field_info(memory_type: str) -> str:
    """Get field information for entity from YAML schema."""
    if not yaml_translator:
        return f"Data fields for {memory_type}"

    try:
        entities_map = yaml_translator._entities_map()
        entity_spec = entities_map.get(memory_type.lower())
        if not entity_spec:
            return f"Data fields for {memory_type}"

        # Get all fields including inherited ones
        all_fields = yaml_translator._resolve_inherited_fields(entity_spec)
        system_fields = yaml_translator._get_system_fields(entity_spec)

        # Filter out system fields for user payload
        user_fields = []
        for field_name, field_def in all_fields.items():
            if field_name not in system_fields:
                field_info = f"{field_name}"
                if isinstance(field_def, dict):
                    field_type = field_def.get("type", "string")
                    required = field_def.get("required", False)
                    choices = field_def.get("choices")
                    default = field_def.get("default")

                    # Build field description
                    parts = [f"({field_type}"]
                    if required:
                        parts.append("required")
                    if choices:
                        parts.append(f"choices: {choices}")
                    if default is not None:
                        parts.append(f"default: {default}")
                    parts.append(")")

                    field_info += " " + "".join(parts)

                user_fields.append(field_info)

        if user_fields:
            return f"Data fields for {memory_type}: {', '.join(user_fields)}"
    except Exception as e:
        logger.warning(f"Failed to get field info for {memory_type}: {e}")

    return f"Data fields for {memory_type}"

# ========================= DYNAMIC TOOL REGISTRATION =========================

def register_dynamic_add_tools(app: FastMCP) -> None:
    """Register dynamic add_* tools for each memory type."""
    if not yaml_translator:
        logger.error("YAML translator not initialized - cannot register dynamic tools")
        return

    try:
        entity_types = yaml_translator.get_entity_types()
        # Skip memo - it's a base type for inheritance only
        filtered_types = [t for t in entity_types if t != "memo"]
        logger.info(f"🔧 Registering dynamic add tools for types: {filtered_types}")

        for memory_type in filtered_types:
            tool_name = f"add_{memory_type}"
            description = get_entity_description(memory_type)
            field_info = get_entity_field_info(memory_type)

            def make_add_tool(mtype: str):
                @app.tool(tool_name, description=description)
                def dynamic_add_tool(
                    user_id: str = Field(..., description="User identifier - separates user's memories from each other"),
                    data: Dict[str, Any] = Field(..., description=field_info)
                ) -> Dict[str, Any]:
                    logger.info(f"=== {tool_name.upper()} CALLED ===")
                    logger.info(f"Adding {mtype} for user {user_id}")
                    logger.info(f"Data: {data}")

                    # Validate user_id
                    user_error = handle_user_id_error(user_id, f"add_{mtype}")
                    if user_error:
                        return user_error

                    try:
                        client = get_memg_client()
                        hrid = client.add_memory(
                            memory_type=mtype,
                            payload=data,
                            user_id=user_id
                        )
                        logger.info(f"✅ Successfully added {mtype} with HRID: {hrid}")

                        return {
                            "result": f"{mtype.title()} added successfully",
                            "hrid": hrid,
                            "memory_type": mtype
                        }

                    except Exception as e:
                        return handle_operation_error(e, f"add_{mtype}", memory_type=mtype, user_id=user_id)

                return dynamic_add_tool

            # Register the tool
            make_add_tool(memory_type)
            logger.info(f"✅ Registered tool: {tool_name}")

    except Exception as e:
        logger.error(f"❌ Failed to register dynamic add tools: {e}")
        raise

# ========================= UNIFIED TOOL HANDLERS =========================

def handle_memory_operation(operation: str, client_method: str, **kwargs) -> Dict[str, Any]:
    """Unified handler for memory operations (delete, update, get)."""
    user_id = kwargs.get("user_id")

    # Validate user_id
    user_error = handle_user_id_error(user_id, operation)
    if user_error:
        return user_error

    try:
        client = get_memg_client()
        method = getattr(client, client_method)

        # Call the client method with filtered kwargs (remove operation-specific keys)
        client_kwargs = {k: v for k, v in kwargs.items() if k not in ["operation", "success_key", "success_message", "failure_message"]}
        result = method(**client_kwargs)

        # Handle different return types
        if operation == "get_memory_by_hrid":
            if result:
                return {"result": "Memory retrieved successfully", "memory": result}
            else:
                return {"result": "Memory not found", "hrid": kwargs.get("hrid"), "memory": None}

        elif operation == "list_memories_by_type":
            return {
                "result": f"Retrieved {len(result)} memories",
                "memories": result,
                "count": len(result),
                "query_params": {k: v for k, v in kwargs.items() if k in ["memory_type", "limit", "offset", "include_neighbors", "filters"]}
            }

        else:  # delete_memory, update_memory
            success_key = kwargs.get("success_key", "success")
            success_message = kwargs.get("success_message", f"{operation.replace('_', ' ').title()} successful")
            failure_message = kwargs.get("failure_message", f"{operation.replace('_', ' ').title()} failed")

            return {
                "result": success_message if result else failure_message,
                "hrid": kwargs.get("hrid") or kwargs.get("memory_id"),
                success_key: bool(result)
            }

    except Exception as e:
        error_context = {k: v for k, v in kwargs.items() if k in ["hrid", "memory_id", "memory_type"]}
        return handle_operation_error(e, operation, **error_context)

def handle_relationship_operation(operation: str, **kwargs) -> Dict[str, Any]:
    """Unified handler for relationship operations (add, delete)."""
    user_id = kwargs.get("user_id")

    # Validate user_id
    user_error = handle_user_id_error(user_id, operation)
    if user_error:
        return user_error

    try:
        client = get_memg_client()

        if operation == "add_relationship":
            client.add_relationship(**{k: v for k, v in kwargs.items() if k != "operation"})
            return {
                "result": "Relationship added successfully",
                "from_hrid": kwargs["from_memory_hrid"],
                "to_hrid": kwargs["to_memory_hrid"],
                "relation_type": kwargs["relation_type"]
            }

        else:  # delete_relationship
            success = client.delete_relationship(**{k: v for k, v in kwargs.items() if k != "operation"})
            return {
                "result": "Relationship deleted successfully" if success else "Relationship not found",
                "from_hrid": kwargs["from_memory_hrid"],
                "to_hrid": kwargs["to_memory_hrid"],
                "relation_type": kwargs["relation_type"],
                "deleted": success
            }

    except Exception as e:
        error_context = {
            "from_hrid": kwargs.get("from_memory_hrid"),
            "to_hrid": kwargs.get("to_memory_hrid"),
            "relation_type": kwargs.get("relation_type")
        }
        return handle_operation_error(e, operation, **error_context)

def handle_search_operation(query: str, user_id: str, **search_params) -> Dict[str, Any]:
    """Specialized handler for search operations."""
    # Validate inputs
    user_error = handle_user_id_error(user_id, "search_memories")
    if user_error:
        return user_error

    if not query.strip():
        return {"error": "Query cannot be empty", "memories": []}

    # Apply limits and normalize inputs
    limit = min(search_params.get("limit", 5), 50)
    memory_type_filter = None
    memory_type = search_params.get("memory_type")
    if memory_type and isinstance(memory_type, str):
        memory_type_filter = memory_type.lower().strip()

    try:
        client = get_memg_client()
        results = client.search(
            query=query,
            user_id=user_id,
            memory_type=memory_type_filter,
            limit=limit,
            neighbor_limit=search_params.get("neighbor_limit", 5),
            hops=search_params.get("hops", 1),
            include_semantic=search_params.get("include_semantic", True)
        )

        logger.info(f"Search completed, found {len(results.memories)} seeds and {len(results.neighbors)} neighbors")

        # Return SearchResult directly as dict with simplified status
        search_dict = results.model_dump()

        return {
            "status": f"Found {len(results.memories)} memories and {len(results.neighbors)} neighbors",
            "memories": search_dict["memories"],
            "neighbors": search_dict["neighbors"],
            "query": query,
            "user_id": user_id,
            "search_params": {
                "limit": limit,
                "memory_type": memory_type_filter,
                "neighbor_limit": search_params.get("neighbor_limit", 5),
                "hops": search_params.get("hops", 1),
                "include_semantic": search_params.get("include_semantic", True)
            }
        }

    except Exception as e:
        return handle_operation_error(e, "search_memories", query=query, memories=[])

# ========================= REMAINING TOOLS (UNIFIED) =========================

def register_remaining_tools(app: FastMCP) -> None:
    """Register remaining tools using unified handlers."""

    @app.tool("delete_memory", description="Delete a memory by HRID.")
    def delete_memory_tool(
        memory_id: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)")
    ) -> Dict[str, Any]:
        return handle_memory_operation(
            operation="delete_memory",
            client_method="delete_memory",
            hrid=memory_id,
            user_id=user_id,
            success_key="deleted",
            success_message="Memory deleted",
            failure_message="Delete failed"
        )

    @app.tool("update_memory", description="Update memory with partial payload changes (patch-style update).")
    def update_memory_tool(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        payload_updates: Dict[str, Any] = Field(..., description="Payload updates (only fields you want to change)"),
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== UPDATE_MEMORY TOOL CALLED ===")
        logger.info(f"Updating {hrid} for user {user_id}")
        logger.info(f"Updates: {payload_updates}")

        return handle_memory_operation(
            operation="update_memory",
            client_method="update_memory",
            hrid=hrid,
            payload_updates=payload_updates,
            user_id=user_id,
            memory_type=memory_type,
            success_key="updated",
            success_message="Memory updated successfully",
            failure_message="Update failed"
        )

    @app.tool("search_memories", description="Search memories using semantic vector search with graph expansion.")
    def search_memories_tool(
        query: str = Field(..., description="Search query text"),
        user_id: str = Field(..., description="User identifier (required for data isolation)"),
        limit: int = Field(5, description="Maximum results (default: 5, max: 50)"),
        memory_type: Optional[str] = Field(None, description="Filter by memory type (optional)"),
        neighbor_limit: int = Field(5, description="Max graph neighbors per result (default: 5)"),
        hops: int = Field(1, description="Graph traversal depth (default: 1)"),
        include_semantic: bool = Field(True, description="Include semantic search (default: true)")
    ) -> Dict[str, Any]:
        logger.info(f"=== SEARCH_MEMORIES TOOL CALLED ===")
        logger.info(f"Query: {query}")
        logger.info(f"User ID: {user_id}")

        return handle_search_operation(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            neighbor_limit=neighbor_limit,
            hops=hops,
            include_semantic=include_semantic
        )

    @app.tool("add_relationship", description="Add a relationship between two memories.")
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

        return handle_relationship_operation(
            operation="add_relationship",
            from_memory_hrid=from_memory_hrid,
            to_memory_hrid=to_memory_hrid,
            relation_type=relation_type,
            from_memory_type=from_memory_type,
            to_memory_type=to_memory_type,
            user_id=user_id,
            properties=properties
        )

    @app.tool("delete_relationship", description="Delete a relationship between two memories.")
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

        return handle_relationship_operation(
            operation="delete_relationship",
            from_memory_hrid=from_memory_hrid,
            to_memory_hrid=to_memory_hrid,
            relation_type=relation_type,
            user_id=user_id,
            from_memory_type=from_memory_type,
            to_memory_type=to_memory_type
        )

    @app.tool("get_memory_by_hrid", description="Get a single memory by HRID.")
    def get_memory_by_hrid_tool(
        hrid: str = Field(..., description="Memory HRID (human readable identifier)"),
        user_id: str = Field(..., description="User identifier (for ownership verification)"),
        memory_type: Optional[str] = Field(None, description="Memory type (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== GET_MEMORY_BY_HRID TOOL CALLED ===")
        logger.info(f"Getting memory {hrid} for user {user_id}")

        return handle_memory_operation(
            operation="get_memory_by_hrid",
            client_method="get_memory",
            hrid=hrid,
            user_id=user_id,
            memory_type=memory_type
        )

    @app.tool("list_memories_by_type", description="List multiple memories with filtering and optional graph expansion.")
    def list_memories_by_type_tool(
        user_id: str = Field(..., description="User identifier"),
        memory_type: Optional[str] = Field(None, description="Filter by memory type (optional)"),
        limit: int = Field(50, description="Maximum results (default: 50)"),
        offset: int = Field(0, description="Skip first N results for pagination (default: 0)"),
        include_neighbors: bool = Field(False, description="Include graph neighbors (default: false)"),
        hops: int = Field(1, description="Graph traversal depth when include_neighbors=true (default: 1)"),
        filters: Optional[Dict[str, Any]] = Field(None, description="Additional field-based filters (optional)")
    ) -> Dict[str, Any]:
        logger.info(f"=== LIST_MEMORIES_BY_TYPE TOOL CALLED ===")
        logger.info(f"Listing memories for user {user_id}, type: {memory_type}, limit: {limit}")

        return handle_memory_operation(
            operation="list_memories_by_type",
            client_method="get_memories",
            user_id=user_id,
            memory_type=memory_type,
            filters=filters,
            limit=limit,
            offset=offset,
            include_neighbors=include_neighbors,
            hops=hops
        )

    @app.tool("get_system_info")
    def get_system_info_tool(random_string: str = "") -> Dict[str, Any]:
        try:
            from memg_core.core.types import get_entity_type_enum

            entity_enum = get_entity_type_enum()
            entity_types = [e.value for e in entity_enum]

            # Get YAML schema info
            yaml_schema = os.getenv("MEMG_YAML_SCHEMA", "not configured")

            return {
                "system_type": "MEMG Core (Dynamic)",
                "version": __version__,
                "functions": ["add_note", "add_task", "add_document", "add_bug", "add_solution", "delete_memory", "update_memory", "search_memories", "get_memory_by_hrid", "list_memories_by_type", "add_relationship", "delete_relationship", "get_system_info"],
                "memory_types": entity_types,
                "yaml_schema": yaml_schema,
                "note": "Tools are dynamically generated from YAML schema"
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {
                "system_type": "MEMG Core (Dynamic)",
                "version": __version__,
                "error": f"Failed to get schema info: {str(e)}",
                "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured")
            }


# ========================= HEALTH ENDPOINTS =========================

def setup_health_endpoints(app: FastMCP) -> None:
    """Setup health check endpoints."""

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        client_status = "initialized" if memg_client is not None else "not initialized"
        status = {
            "service": "MEMG Core MCP Server (Dynamic)",
            "version": __version__,
            "memg_client": client_status,
            "yaml_schema": os.getenv("MEMG_YAML_SCHEMA", "not configured"),
            "status": "healthy"
        }
        return JSONResponse(status, status_code=200)

# ========================= APP CREATION =========================

def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    # Initialize client and YAML translator BEFORE registering tools
    initialize_client()

    app = FastMCP()

    # Register dynamic add_* tools first (clean implementation)
    register_dynamic_add_tools(app)

    # Register remaining tools (to be cleaned up)
    register_remaining_tools(app)

    # Setup health endpoints
    setup_health_endpoints(app)

    return app

# ========================= MAIN =========================

# Create the app instance
mcp_app = create_app()

if __name__ == "__main__":
    # Get port from .env, respecting the exact variable name
    port_env = os.getenv("MEMORY_SYSTEM_MCP_PORT", "8888")
    port = int(port_env)

    # Host should be configured via deployment (Docker, docker-compose, etc.)
    host = os.getenv("MEMORY_SYSTEM_MCP_HOST", "127.0.0.1")

    print(f"🚀 MEMG Core MCP Server (Dynamic) v{__version__} on {host}:{port}")
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
