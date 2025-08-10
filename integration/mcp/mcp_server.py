#!/usr/bin/env python3
"""
Minimal MEMG MCP Server - Thin bridge over the published memg-core library.

This file intentionally keeps the MCP integration small and dependency-light.
It initializes the SyncMemorySystem and exposes a few essential MCP tools.
"""

import os
from typing import Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from memory_system.logging_config import get_logger, log_error
from integration.sync_wrapper import SyncMemorySystem

logger = get_logger("mcp_server")


# ------------------------- App + Memory Init -------------------------
memory: Optional[SyncMemorySystem] = None


def initialize_memory_system() -> Optional[SyncMemorySystem]:
    global memory
    try:
        memory = SyncMemorySystem()
        logger.info("Memory system initialized successfully (minimal MCP)")
        return memory
    except Exception as e:
        log_error("mcp_server", "memory_initialization", e)
        memory = None
        return None


def setup_health_endpoints(app: FastMCP) -> None:
    try:
        from memory_system.version import __version__  # generated in package
    except Exception:
        __version__ = os.getenv("MEMORY_SYSTEM_VERSION", "0.0.0")

    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        return JSONResponse({"status": "healthy", "service": f"MEMG MCP v{__version__}"})

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        status = {
            "service": "MEMG MCP",
            "version": __version__,
            "memory_system_initialized": memory is not None,
            "status": "healthy" if memory is not None else "unhealthy",
        }
        return JSONResponse(status, status_code=200 if memory else 503)


def register_tools(app: FastMCP) -> None:
    @app.tool("mcp_gmem_add_memory")
    def add_memory(content: str, user_id: str, memory_type: str = None, title: str = None,
                   source: str = "mcp_api", tags: str = None):
        if not memory:
            return {"result": "❌ Memory system not initialized"}
        try:
            from memory_system.models.core import MemoryType

            parsed_type = None
            if memory_type:
                name = memory_type.strip().upper()
                if name in MemoryType.__members__:
                    parsed_type = MemoryType[name]
                else:
                    return {"result": f"❌ Invalid memory_type: {memory_type}"}

            parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
            resp = memory.add(
                content=content,
                user_id=user_id,
                memory_type=parsed_type,
                title=title,
                source=source,
                tags=parsed_tags,
            )
            return {
                "result": "✅ Memory added" if resp.success else "❌ Failed to add memory",
                "memory_id": resp.memory_id,
                "final_type": getattr(resp.final_type, "value", None),
                "word_count": resp.word_count,
            }
        except Exception as e:
            log_error("mcp_server", "add_memory", e)
            return {"result": f"❌ Error: {e}"}

    @app.tool("mcp_gmem_search_memories")
    def search_memories(query: str, user_id: str = None, limit: int = 5):
        if not memory:
            return {"result": "❌ Memory system not initialized"}
        try:
            results = memory.search(query=query, user_id=user_id, limit=limit)
            return {"result": results}
        except Exception as e:
            log_error("mcp_server", "search_memories", e)
            return {"result": f"❌ Error: {e}"}

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info():
        if not memory:
            return {"result": {"components_initialized": False, "status": "Not initialized"}}
        try:
            stats = memory.get_stats()
            # Optionally enrich using core system info when available
            try:
                from memory_system.utils.system_info import get_system_info as core_info

                enriched = core_info(qdrant=memory.qdrant_interface)
                stats.update({"core": enriched})
            except Exception:
                pass
            port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))
            stats.update({"transport": "SSE", "port": port})
            return {"result": stats}
        except Exception as e:
            log_error("mcp_server", "get_system_info", e)
            return {"result": f"❌ Error: {e}"}


def create_app() -> FastMCP:
    app = FastMCP()
    initialize_memory_system()
    setup_health_endpoints(app)
    register_tools(app)
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))
    logger.info(f"Starting MEMG MCP Server on port {port}")
    app.run(transport="sse", host="0.0.0.0", port=port)  # nosec
