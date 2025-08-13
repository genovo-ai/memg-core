#!/usr/bin/env python3
"""
Minimal MEMG MCP Server - Clean bridge over the published memg-core library.

This is a thin MCP integration that uses only the memg-core library APIs.
No custom wrappers or sync_wrapper dependencies.
"""

import asyncio
import os
from typing import Any, Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

import memg_core
from memg_core.config import get_config
from memg_core.kuzu_graph.interface import KuzuInterface
from memg_core.logging_config import get_logger, log_error
from memg_core.models.api import MemoryResultItem, SearchMemoriesResponse
from memg_core.models.core import MemoryType
from memg_core.processing.memory_retriever import MemoryRetriever
from memg_core.qdrant.interface import QdrantInterface
from memg_core.utils.embeddings import GenAIEmbedder

logger = get_logger("mcp_server")


class MinimalMemoryBridge:
    """Minimal bridge that uses memg-core library directly."""

    def __init__(self) -> None:
        self.system_config = get_config()
        self.memg_config = self.system_config.memg

        self.qdrant_interface = QdrantInterface()
        self.kuzu_interface = KuzuInterface()
        self.retriever = MemoryRetriever(
            qdrant_interface=self.qdrant_interface,
            kuzu_interface=self.kuzu_interface,
        )
        self.embedder = GenAIEmbedder()

    def add(
        self,
        content: str,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        title: Optional[str] = None,
        source: str = "mcp_api",
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> dict[str, Any]:
        final_type = memory_type or MemoryType.NOTE

        # Determine embedding text
        if final_type == MemoryType.DOCUMENT:
            index_text = f"{title}. {content}" if title else content
        elif final_type == MemoryType.TASK:
            index_text = f"{title}. {content}" if title else content
        else:
            index_text = content

        vector = self.embedder.get_embedding(index_text)

        # Ensure collection exists
        self.qdrant_interface.ensure_collection(
            self.memg_config.qdrant_collection_name, len(vector)
        )

        payload = {
            "user_id": user_id,
            "content": content,
            "memory_type": final_type.value,
            "title": title,
            "source": source,
            "tags": tags or [],
            "project_id": project_id,
            "project_name": project_name,
            "is_valid": True,
            "index_text": index_text,
            "created_at": __import__("datetime")
            .datetime.now(__import__("datetime").timezone.utc)
            .isoformat(),
        }

        success, point_id = self.qdrant_interface.add_point(
            vector=vector,
            payload=payload,
            point_id=None,
            collection=self.memg_config.qdrant_collection_name,
        )

        # Add to Kuzu
        self.kuzu_interface.add_node(
            "Memory",
            {
                "id": point_id,
                "user_id": user_id,
                "project_id": project_id or "",
                "project_name": project_name or "",
                "content": content,
                "memory_type": final_type.value,
                "summary": "",
                "title": title or "",
                "source": source or "",
                "tags": ",".join(tags or []),
                "confidence": 0.8,
                "is_valid": True,
                "created_at": payload["created_at"],
                "expires_at": "",
                "supersedes": "",
                "superseded_by": "",
            },
        )

        return {
            "success": bool(success),
            "memory_id": point_id,
            "final_type": final_type.value,
            "word_count": len(content.split()),
        }

    async def search_async(
        self, query: str, user_id: Optional[str], limit: int
    ) -> list[dict[str, Any]]:
        results = await self.retriever.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            score_threshold=self.memg_config.score_threshold,
        )
        return [
            {
                "content": r.memory.content,
                "type": r.memory.memory_type.value,
                "summary": r.memory.summary,
                "score": r.score,
                "source": r.memory.source or "unknown",
                "memory_id": r.memory.id,
                "title": r.memory.title,
                "tags": r.memory.tags,
                "word_count": r.memory.word_count(),
                "created_at": r.memory.created_at.isoformat(),
            }
            for r in results
        ]

    def search(
        self, query: str, user_id: Optional[str], limit: int = 5
    ) -> list[dict[str, Any]]:
        return asyncio.run(self.search_async(query, user_id, limit))

    def get_stats(self) -> dict[str, Any]:
        return {
            "retriever_initialized": self.retriever is not None,
            "qdrant_available": self.qdrant_interface is not None,
            "kuzu_available": self.kuzu_interface is not None,
            "system_type": "memg_core_mcp_bridge",
            "memg_config": self.memg_config.to_dict(),
        }


# ------------------------- App + Memory Init -------------------------
memory: Optional[MinimalMemoryBridge] = None


def initialize_memory_system() -> Optional[MinimalMemoryBridge]:
    global memory
    memory = MinimalMemoryBridge()
    return memory


def setup_health_endpoints(app: FastMCP) -> None:
    @app.custom_route("/", methods=["GET"])
    async def root(_req):
        return JSONResponse(
            {"status": "healthy", "service": f"MEMG MCP v{memg_core.__version__}"}
        )

    @app.custom_route("/health", methods=["GET"])
    async def health(_req):
        status = {
            "service": "MEMG MCP",
            "version": memg_core.__version__,
            "memory_system_initialized": memory is not None,
            "status": "healthy" if memory is not None else "unhealthy",
        }
        return JSONResponse(status, status_code=200 if memory else 503)


def register_tools(app: FastMCP) -> None:
    @app.tool("mcp_gmem_add_memory")
    def add_memory(
        content: str,
        user_id: str,
        memory_type: str = None,
        title: str = None,
        source: str = "mcp_api",
        tags: str = None,
    ):
        if not memory:
            return {"result": "❌ Memory system not initialized"}
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
            "result": (
                "✅ Memory added" if resp["success"] else "❌ Failed to add memory"
            ),
            "memory_id": resp["memory_id"],
            "final_type": resp["final_type"],
            "word_count": resp["word_count"],
        }

    @app.tool("mcp_gmem_search_memories")
    def search_memories(query: str, user_id: str = None, limit: int = 5):
        if not memory:
            return {"result": "❌ Memory system not initialized"}
        results = memory.search(query=query, user_id=user_id, limit=limit)
        return {"result": results}

    @app.tool("mcp_gmem_get_system_info")
    def get_system_info():
        if not memory:
            return {
                "result": {"components_initialized": False, "status": "Not initialized"}
            }
        stats = memory.get_stats()
        # Optionally enrich using core system info when available
        try:
            from memg_core.utils.system_info import get_system_info as core_info

            enriched = core_info(qdrant=memory.qdrant_interface)
            stats.update({"core": enriched})
        except Exception:
            pass
        port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))
        stats.update({"transport": "SSE", "port": port})
        return {"result": stats}


def create_app() -> FastMCP:
    app = FastMCP()
    initialize_memory_system()
    setup_health_endpoints(app)
    register_tools(app)
    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("MEMORY_SYSTEM_MCP_PORT", "8787"))

    app.run(transport="sse", host="0.0.0.0", port=port)  # nosec
