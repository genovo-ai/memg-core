#!/usr/bin/env python3
"""
MEMG MCP Server Core - Initialization and Health Endpoints
Handles system initialization, memory setup, and health checking
"""

import os
from typing import Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from memory_system.exceptions import ConfigurationError, ProcessingError, ValidationError
from memory_system.logging_config import get_logger, log_error
from memory_system.sync_wrapper import SyncMemorySystem

# ------------------------- Version -------------------------
try:
    from memory_system.version import __version__
except Exception:
    __version__ = os.getenv("MEMORY_SYSTEM_VERSION", "0.0.0")

# ------------------------- Logging -------------------------
logger = get_logger("mcp_server_core")

# ------------------------- Memory System Initialization -------------------------
memory: Optional[SyncMemorySystem] = None


def initialize_memory_system() -> Optional[SyncMemorySystem]:
    """Initialize the memory system with proper error handling"""
    global memory

    try:
        memory = SyncMemorySystem()
        logger.info("Memory system initialized successfully")

        # Optional templates initialization - non-fatal
        try:
            from memory_system.template_init import initialize_templates

            initialize_templates()
            logger.info("Template system initialized successfully")
        except Exception as e:
            logger.warning(f"Template system initialization failed: {e}")

        return memory

    except Exception as e:
        log_error("mcp_server_core", "memory_initialization", e)
        memory = None
        return None


def get_memory_system() -> Optional[SyncMemorySystem]:
    """Get the initialized memory system"""
    return memory


def setup_health_endpoints(app: FastMCP) -> None:
    """Setup health check endpoints for the MCP server"""

    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        """Root endpoint for basic health check"""
        return JSONResponse({"status": "healthy", "service": f"MEMG MCP v{__version__}"})

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        """Detailed health check endpoint"""
        health_status = {
            "service": "MEMG MCP",
            "version": __version__,
            "memory_system_initialized": memory is not None,
            "status": "healthy",
        }

        if memory:
            try:
                stats = memory.get_stats()
                health_status["components"] = {
                    "processor": stats.get("processor_initialized", False),
                    "retriever": stats.get("retriever_initialized", False),
                    "qdrant": stats.get("qdrant_available", False),
                    "kuzu": stats.get("kuzu_available", False),
                }
            except Exception as e:
                health_status["status"] = "degraded"
                health_status["error"] = f"System error: {str(e)}"
                log_error("mcp_server_core", "health_check", e)
        else:
            health_status["status"] = "unhealthy"
            health_status["error"] = "Memory system not initialized"

        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(health_status, status_code=status_code)


def create_mcp_app() -> FastMCP:
    """Create and configure the FastMCP application"""
    app = FastMCP()

    # Initialize memory system
    initialize_memory_system()

    # Setup health endpoints
    setup_health_endpoints(app)

    return app
