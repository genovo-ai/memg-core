#!/usr/bin/env python3
"""
MEMG Core MCP Server - Updated for lean core API.

This MCP server uses the latest memg-core public API with the lean core architecture.
"""

import os
from typing import Any, Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

# Import the new lean core public API
from memg_core.api.public import add_memory, search
from memg_core.core.models import SearchResult
from memg_core import __version__
from memg_core.core.yaml_translator import get_yaml_translator
from memg_core.core.exceptions import ValidationError


def get_dynamic_tool_docstring() -> str:
    """Generates a dynamic docstring for the add_memory tool from the YAML schema."""
    try:
        translator = get_yaml_translator()
        spec_map = translator._entities_map()

        doc = "Adds a memory to the system based on a dynamic, YAML-defined schema.\n\n"
        doc += "Args:\n"
        doc += "    memory_type (str): The type of memory to add (must be defined in YAML schema).\n"
        doc += "    user_id (str): The user ID to associate with the memory.\n"
        doc += "    payload (dict): A dictionary of fields conforming to the schema for the given memory_type.\n\n"
        doc += "Available Schemas:\n"

        for name, spec_data in spec_map.items():
            spec = translator.get_entity_spec(name)
            doc += f"  - memory_type: '{spec.name}'\n"
            doc += f"    Anchor Field: '{spec.anchor}'\n"
            doc += f"    Fields:\n"
            if spec.fields:
                for field_name, props in spec.fields.items():
                    if props.get('system'):
                        continue
                    req_str = " (required)" if props.get('required') else ""
                    type_str = props.get('type', 'any')
                    doc += f"      - {field_name}: {type_str}{req_str}\n"
        return doc
    except Exception as e:
        return f"Could not generate dynamic docstring. Error: {e}"


class MemgCoreBridge:
    """A lean bridge to the memg-core public API."""

    def add_memory(self, memory_type: str, user_id: str, payload: dict, tags: Optional[list[str]] = None) -> dict[str, Any]:
        """Directly calls the generic add_memory function."""
        try:
            memory = add_memory(
                memory_type=memory_type,
                user_id=user_id,
                payload=payload,
                tags=tags or []
            )
            return {
                "success": True,
                "memory_id": memory.id,
                "hrid": memory.hrid,
            }
        except ValidationError as e:
            return {"success": False, "error": f"Validation Error: {e}"}
        except Exception as e:
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
                    "tags": r.memory.tags,
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
    bridge = MemgCoreBridge()
    return bridge


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
    def add_memory_tool(memory_type: str, user_id: str, payload: dict, tags: str = None):
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        result = bridge.add_memory(
            memory_type=memory_type,
            user_id=user_id,
            payload=payload,
            tags=parsed_tags
        )

        if result["success"]:
            return {
                "result": f"✅ {memory_type.title()} added successfully",
                "memory_id": result["memory_id"],
                "hrid": result.get("hrid"),
            }
        else:
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
        mode: str = "vector"
    ):
        """Search memories with the lean core search function."""
        if not bridge:
            return {"result": "❌ Bridge not initialized"}

        results = bridge.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            memory_type=memory_type,
            mode=mode
        )

        if results and "error" in results[0]:
            return {"result": f"❌ Search failed: {results[0]['error']}"}

        return {
            "result": f"✅ Found {len(results)} memories",
            "memories": results,
        }

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info_tool():
        """Get system information and available memory schemas."""
        if not bridge:
            return {"result": {"status": "Bridge not initialized"}}

        stats = bridge.get_stats()
        try:
            translator = get_yaml_translator()
            stats["yaml_schemas"] = translator._entities_map()
        except Exception as e:
            stats["yaml_schemas"] = {"error": f"Could not load schemas: {e}"}

        return {"result": stats}


def create_app() -> FastMCP:
    """Create and configure the FastMCP app."""
    app = FastMCP()
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
