#!/usr/bin/env python3
"""
MEMG Core MCP Server - Updated for lean core API.

This MCP server uses the latest memg-core public API with the lean core architecture.
"""

import os
from pathlib import Path
import logging
from typing import Any, Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

# Import the new lean core public API
from memg_core.api.public import add_memory, search
from memg_core.core.models import SearchResult
from memg_core import __version__
from memg_core.core.yaml_translator import get_yaml_translator
from memg_core.core.exceptions import ValidationError

# Setup comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _ensure_yaml_schema_env() -> None:
    """Ensure MEMG_YAML_SCHEMA is explicitly set.

    - Uses MEMG_YAML_SCHEMA from environment or falls back to defaults
    This sets the environment variable explicitly to satisfy the strict
    requirement of the YAML translator while keeping server DX smooth.
    """
    if os.getenv("MEMG_YAML_SCHEMA"):
        logger.info(f"📄 Using YAML schema from MEMG_YAML_SCHEMA={os.getenv('MEMG_YAML_SCHEMA')}")
        return

    # Normalize repo-relative path to container path
    env_val = os.getenv("MEMG_YAML_SCHEMA")
    if env_val and not env_val.startswith("/app/"):
        # If a repo-relative path is provided (e.g., from .env),
        # translate it to the container path under /app.
        candidate = Path("/app") / env_val
        if candidate.exists():
            os.environ["MEMG_YAML_SCHEMA"] = str(candidate)
            logger.info(f"🧭 Normalized MEMG_YAML_SCHEMA to container path: {candidate}")
            return

    # Fallback: should not happen with proper .env setup
    logger.warning("⚠️ MEMG_YAML_SCHEMA not properly set. Ensure .env file is configured.")


def _summarize_entity_fields(translator) -> dict[str, dict[str, list[str]]]:
    """Build a summary of required/optional fields for each entity from YAML.

    System fields are hidden since they are handled internally.
    """
    summary: dict[str, dict[str, list[str]]] = {}
    for name, spec in translator._entities_map().items():
        fields = spec.get("fields", {})
        required: list[str] = []
        optional: list[str] = []
        if isinstance(fields, dict):
            for field_name, cfg in fields.items():
                # Skip system fields
                if isinstance(cfg, dict) and cfg.get("system"):
                    continue
                is_required = isinstance(cfg, dict) and cfg.get("required") is True
                (required if is_required else optional).append(str(field_name))
        summary[name] = {"required": sorted(required), "optional": sorted(optional)}
    return summary


def get_dynamic_tool_docstring() -> str:
    """Generates a dynamic docstring for the add_memory tool from the YAML schema."""
    try:
        translator = get_yaml_translator()
        spec_map = translator._entities_map()
        field_summary = _summarize_entity_fields(translator)

        doc = "Adds a memory to the system based on a dynamic, YAML-defined schema.\n\n"
        doc += "Args:\n"
        doc += "    memory_type (str): The type of memory to add (must be defined in YAML schema).\n"
        doc += "    user_id (str): The user ID to associate with the memory.\n"
        doc += "    payload (dict): A dictionary of fields conforming to the schema for the given memory_type.\n\n"
        doc += "Available Schemas:\n"

        for name, _spec in spec_map.items():
            req = ", ".join(field_summary.get(name, {}).get("required", [])) or "(none)"
            opt = ", ".join(field_summary.get(name, {}).get("optional", [])) or "(none)"
            doc += f"  - memory_type: '{name}'\n"
            doc += f"    Anchor Field: '{translator.get_anchor_field(name)}'\n"
            doc += f"    Required fields: {req}\n"
            doc += f"    Optional fields: {opt}\n"
        return doc
    except Exception as e:
        return f"Could not generate dynamic docstring. Error: {e}"


class MemgCoreBridge:
    """A lean bridge to the memg-core public API."""

    def add_memory(self, memory_type: str, user_id: str, payload: dict) -> dict[str, Any]:
        """Directly calls the generic add_memory function with YAML-validated payload."""
        logger.info(f"🚀 Starting add_memory: type={memory_type}, user={user_id}, payload={payload}")
        try:
            logger.debug(f"📝 Calling core add_memory function...")
            memory = add_memory(
                memory_type=memory_type,
                user_id=user_id,
                payload=payload
            )
            logger.info(f"✅ Memory created successfully: id={memory.id}, hrid={memory.hrid}")
            return {
                "success": True,
                "memory_id": memory.id,
                "hrid": memory.hrid,
            }
        except ValidationError as e:
            logger.error(f"❌ Validation Error: {e}")
            return {"success": False, "error": f"Validation Error: {e}"}
        except Exception as e:
            logger.error(f"💥 Unexpected Error in add_memory: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        **kwargs
    ) -> list[dict[str, Any]]:
        """Search memories using the lean core search function."""
        try:
            results: list[SearchResult] = search(
                query=query,
                user_id=user_id,
                limit=limit,
                memo_type=kwargs.get("memory_type"),
                mode=kwargs.get("mode", "vector"),
                include_details=kwargs.get("include_details", "self")
            )

            # The `__getattr__` on Memory model allows generic access to payload.
            return [
                {
                    "memory_id": r.memory.id,
                    "hrid": r.memory.hrid,
                    "memory_type": r.memory.memory_type,
                    "payload": r.memory.payload,
                    "score": r.score,
                    "source": r.source,
                }
                for r in results
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "system_type": "memg_core_lean_mcp",
            "version": __version__,
            "api_type": "generic_yaml_driven",
            "available_functions": ["add_memory", "search_memories"],
        }


# Global bridge instance
bridge: Optional[MemgCoreBridge] = None


def initialize_bridge() -> MemgCoreBridge:
    """Initialize the MEMG Core bridge."""
    global bridge
    logger.info("🏗️ Initializing MEMG Core bridge...")
    try:
        bridge = MemgCoreBridge()
        logger.info("✅ Bridge initialized successfully")
        return bridge
    except Exception as e:
        logger.error(f"💥 Failed to initialize bridge: {e}", exc_info=True)
        raise


def setup_health_endpoints(app: FastMCP) -> None:
    """Setup health check endpoints."""
    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        return JSONResponse({
            "status": "healthy",
            "service": f"MEMG Core MCP v{__version__}",
            "api": "generic_yaml_driven"
        })

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        status = {
            "service": "MEMG Core MCP",
            "version": __version__,
            "bridge_initialized": bridge is not None,
            "status": "healthy" if bridge is not None else "unhealthy",
        }
        return JSONResponse(status, status_code=200 if bridge else 503)


def register_tools(app: FastMCP) -> None:
    """Register MCP tools."""

    @app.tool("mcp_gmem_add_memory")
    def add_memory_tool(
        memory_type: str,
        user_id: str,
        payload: dict
    ):
        """Add a memory using pure YAML-driven schema validation.

        Args:
            memory_type (str): Type of memory (must be defined in YAML schema)
            user_id (str): User ID to associate with the memory
            payload (dict): Complete payload conforming to YAML schema for the memory_type

        Valid memory types and their required/optional fields are defined in the YAML schema.
        Use the get_system_info tool to see available schemas and field requirements.

        Example payloads:
        - memo: {"statement": "Remember this"}
        - note: {"statement": "Note text", "details": "Additional details"}
        - task: {"statement": "Task description", "details": "More info", "status": "todo", "priority": "high"}
        - document: {"statement": "Document title", "details": "Document content"}
        """
        logger.info(f"🔧 MCP Tool called: add_memory_tool(type={memory_type}, user={user_id}, payload={payload})")

        if not bridge:
            logger.error("❌ Bridge not initialized")
            return {"result": "❌ Bridge not initialized"}

        # Validate that memory_type exists in YAML schema
        try:
            logger.debug(f"🔍 Validating memory_type '{memory_type}' against YAML schema...")
            translator = get_yaml_translator()
            if memory_type not in translator._entities_map():
                available_types = list(translator._entities_map().keys())
                logger.error(f"❌ Invalid memory_type '{memory_type}'. Available: {available_types}")
                return {
                    "result": f"❌ Invalid memory_type '{memory_type}'",
                    "error": f"Available types: {available_types}"
                }
            logger.debug(f"✅ Memory type '{memory_type}' is valid")
        except Exception as e:
            logger.error(f"💥 Schema validation failed: {e}", exc_info=True)
            return {"result": f"❌ Schema validation failed: {e}"}

        logger.debug(f"📞 Calling bridge.add_memory...")
        result = bridge.add_memory(
            memory_type=memory_type,
            user_id=user_id,
            payload=payload
        )
        logger.debug(f"📤 Bridge returned: {result}")

        if result["success"]:
            logger.info(f"🎉 Tool successful: {memory_type} added with ID {result['memory_id']}")
            return {
                "result": f"✅ {memory_type.title()} added successfully",
                "memory_id": result["memory_id"],
                "hrid": result.get("hrid"),
            }
        else:
            logger.error(f"💔 Tool failed: {result.get('error', 'Unknown error')}")
            return {
                "result": f"❌ Failed to add {memory_type}",
                "error": result.get("error", "Unknown error")
            }

    # Dynamically set the docstring from the YAML schema
    add_memory_tool.__doc__ = get_dynamic_tool_docstring()


    @app.tool("mcp_gmem_search_memories")
    def search_memories_tool(
        query: str,
        user_id: str = None,
        limit: int = 5,
        memory_type: str = None,
        mode: str = "vector",
        include_details: str = "self",
    ):
        """Search memories with the lean core search function."""
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        results = bridge.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            mode=mode,
            include_details=include_details,
        )

        if results and "error" in results[0]:
            return {"result": f"❌ Search failed: {results[0]['error']}"}

        return {
            "result": f"✅ Found {len(results)} memories",
            "memories": results,
        }

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info_tool():
        """Get system information and complete YAML schema details."""
        if not bridge:
            return {"result": {"status": "Bridge not initialized"}}

        stats = bridge.get_stats()
        try:
            translator = get_yaml_translator()

            # Build schema info using available translator methods
            schema_details = {}
            for entity_name in translator._entities_map():
                fields = _summarize_entity_fields(translator).get(entity_name, {})
                schema_details[entity_name] = {
                    "anchor_field": translator.get_anchor_field(entity_name),
                    "required_fields": fields.get("required", []),
                    "optional_fields": fields.get("optional", []),
                    "description": "Entity type defined in YAML schema",
                }

            stats["yaml_schema_details"] = schema_details
            stats["valid_memory_types"] = list(translator._entities_map().keys())
            stats["yaml_schema_path"] = os.getenv("MEMG_YAML_SCHEMA")

        except Exception as e:
            stats["yaml_schema_error"] = f"Could not load schemas: {e}"

        return {"result": stats}


def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    app = FastMCP()
    # Ensure YAML schema is explicitly set before initializing tools
    _ensure_yaml_schema_env()
    initialize_bridge()
    setup_health_endpoints(app)
    register_tools(app)
    return app


# Create the app instance
app = create_app()

if __name__ == "__main__":
    port_env = os.getenv("MEMORY_SYSTEM_MCP_PORT")
    if not port_env:
        raise ValueError(
            "MEMORY_SYSTEM_MCP_PORT environment variable is required for multi-instance support. "
            "Set it explicitly (e.g., 8787, 8788, 8789) to avoid port conflicts."
        )
    port = int(port_env)

    # Host should be configured via deployment (Docker, docker-compose, etc.)
    host = os.getenv("MEMORY_SYSTEM_MCP_HOST", "127.0.0.1")  # Secure default: localhost only

    print(f"🚀 Starting MEMG Core MCP Server on {host}:{port}")
    print(f"📦 Using memg-core v{__version__} with a generic, YAML-driven API")
    app.run(transport="sse", host=host, port=port)
