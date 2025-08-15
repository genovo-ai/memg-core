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
from memg_core.api.public import add_note, add_document, add_task, search
from memg_core.core.models import SearchResult
from memg_core import __version__


class MemgCoreBridge:
    """Bridge that uses the new lean core public API."""

    def add_memory(
        self,
        content: str,
        user_id: str,
        memory_type: str = "note",
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        **kwargs
    ) -> dict[str, Any]:
        """Add a memory using the appropriate lean core function."""
        try:
            if memory_type.lower() == "document":
                # For documents, use content as summary and title as title
                memory = add_document(
                    text=kwargs.get("text", content),
                    user_id=user_id,
                    title=title,
                    summary=content,
                    tags=tags or []
                )
            elif memory_type.lower() == "task":
                memory = add_task(
                    text=content,
                    user_id=user_id,
                    title=title,
                    tags=tags or [],
                    due_date=kwargs.get("due_date"),
                    assignee=kwargs.get("assignee")
                )
            else:  # Default to note
                memory = add_note(
                    text=content,
                    user_id=user_id,
                    title=title,
                    tags=tags or []
                )

            return {
                "success": True,
                "memory_id": memory.id,
                "memory_type": memory.memory_type,
                "hrid": memory.hrid,
                "word_count": len(content.split()) if content else 0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "memory_id": None,
            }

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
                mode=kwargs.get("mode", "vector"),  # vector, graph, or hybrid
                include_details=kwargs.get("include_details", "self")
            )

            return [
                {
                    "memory_id": result.memory.id,
                    "content": result.memory.content or "",
                    "title": result.memory.title,
                    "memory_type": result.memory.memory_type,
                    "tags": result.memory.tags,
                    "score": result.score,
                    "source": result.source,
                    "hrid": result.memory.hrid,
                    "created_at": result.memory.created_at.isoformat() if result.memory.created_at else None,
                    "word_count": len((result.memory.content or "").split()),
                }
                for result in results
            ]
        except Exception as e:
            return [{"error": str(e)}]

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics."""
        return {
            "system_type": "memg_core_lean_mcp",
            "version": __version__,
            "api_type": "lean_core_public_api",
            "available_functions": ["add_note", "add_document", "add_task", "search"],
            "storage_paths": {
                "qdrant": os.getenv("QDRANT_STORAGE_PATH", "not_set"),
                "kuzu": os.getenv("KUZU_DB_PATH", "not_set"),
            }
        }


# Global bridge instance
bridge: Optional[MemgCoreBridge] = None


def add_memory_tool(
    content: str,
    user_id: str,
    memory_type: str = "note",
    title: str = None,
    tags: str = None,
    text: str = None,  # For documents
    due_date: str = None,  # For tasks
    assignee: str = None,  # For tasks
):
    """Add a memory (note, document, or task)."""
    if not bridge:
        return {"result": "❌ Bridge not initialized"}

    # Parse tags
    parsed_tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Prepare kwargs
    kwargs = {}
    if text:
        kwargs["text"] = text
    if due_date:
        kwargs["due_date"] = due_date
    if assignee:
        kwargs["assignee"] = assignee

    result = bridge.add_memory(
        content=content,
        user_id=user_id,
        memory_type=memory_type,
        title=title,
        tags=parsed_tags,
        **kwargs
    )

    if result["success"]:
        return {
            "result": f"✅ {memory_type.title()} added successfully",
            "memory_id": result["memory_id"],
            "memory_type": result["memory_type"],
            "hrid": result["hrid"],
            "word_count": result["word_count"],
        }
    else:
        return {
            "result": f"❌ Failed to add {memory_type}",
            "error": result.get("error", "Unknown error")
        }


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
            "api": "lean_core"
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
    def add_memory_tool_wrapper(
        content: str,
        user_id: str,
        memory_type: str = "note",
        title: str = None,
        tags: str = None,
        text: str = None,  # For documents
        due_date: str = None,  # For tasks
        assignee: str = None,  # For tasks
    ):
        """Add a memory (note, document, or task)."""
        return add_memory_tool(
            content=content,
            user_id=user_id,
            memory_type=memory_type,
            title=title,
            tags=tags,
            text=text,
            due_date=due_date,
            assignee=assignee
        )

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
            "query": query,
            "mode": mode
        }

    @app.tool("mcp_gmem_add_note")
    def add_note_tool(text: str, user_id: str, title: str = None, tags: str = None):
        """Add a note memory."""
        return add_memory_tool(
            content=text,
            user_id=user_id,
            memory_type="note",
            title=title,
            tags=tags
        )

    @app.tool("mcp_gmem_add_document")
    def add_document_tool(
        text: str,
        user_id: str,
        title: str = None,
        summary: str = None,
        tags: str = None
    ):
        """Add a document memory."""
        return add_memory_tool(
            content=summary or text[:200] + "..." if len(text) > 200 else text,
            user_id=user_id,
            memory_type="document",
            title=title,
            tags=tags,
            text=text
        )

    @app.tool("mcp_gmem_add_task")
    def add_task_tool(
        text: str,
        user_id: str,
        title: str = None,
        tags: str = None,
        due_date: str = None,
        assignee: str = None
    ):
        """Add a task memory."""
        return add_memory_tool(
            content=text,
            user_id=user_id,
            memory_type="task",
            title=title,
            tags=tags,
            due_date=due_date,
            assignee=assignee
        )

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info_tool():
        """Get system information and statistics."""
        if not bridge:
            return {"result": {"status": "Bridge not initialized"}}

        stats = bridge.get_stats()
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
    port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))
    print(f"🚀 Starting MEMG Core MCP Server on port {port}")
    print(f"📦 Using memg-core v{__version__} with lean core API")
    app.run(transport="sse", host="0.0.0.0", port=port)  # nosec
