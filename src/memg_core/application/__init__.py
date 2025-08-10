#!/usr/bin/env python3
"""Application-level thin orchestration surface for memg-core.

This layer exposes simple functions consumed by integrations (e.g., MCP),
without leaking storage details or embedding policy.
"""

from .memory import (
    add_memory,
    delete_memory,
    get_memory_by_id,
    graph_search,
    search_memories,
    update_memory,
)

__all__ = [
    "add_memory",
    "search_memories",
    "graph_search",
    "get_memory_by_id",
    "update_memory",
    "delete_memory",
]
