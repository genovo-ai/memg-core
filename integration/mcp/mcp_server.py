#!/usr/bin/env python3
"""
MEMG MCP Server - Main Entry Point
Clean, modular architecture with separated concerns
"""

import os

from memory_system.logging_config import get_logger

from .mcp_server_core import create_mcp_app
from .mcp_tools_core import register_core_tools, register_optional_tools

logger = get_logger("mcp_server")


def main():
    """Main entry point for the MCP server"""

    # Create the MCP app with core initialization
    app = create_mcp_app()

    # Register the 6 core tools
    register_core_tools(app)

    # Register any optional tools based on environment flags
    register_optional_tools(app)

    logger.info("MCP server configured with core and optional tools")

    return app


# Create the app instance
app = main()

if __name__ == "__main__":
    # Get port from environment variable, default to 8787 for backward compatibility
    port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))

    logger.info(f"Starting MEMG MCP Server on port {port}")

    # Start the server
    app.run(transport="sse", host="0.0.0.0", port=port)  # nosec
