"""MEMG Core - Lightweight memory system for AI agents"""

# Import the new minimal API module for convenience
from . import api
from .application.memory import (
    add_memory,
    delete_memory,
    get_memory_by_id,
    graph_search,
    search_memories,
    update_memory,
)
from .version import __version__

__all__ = [
    "__version__",
    "add_memory",
    "search_memories",
    "graph_search",
    "get_memory_by_id",
    "update_memory",
    "delete_memory",
    "api",  # Expose the minimal API module
]
