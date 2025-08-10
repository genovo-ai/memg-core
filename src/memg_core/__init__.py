"""MEMG Core - Lightweight memory system for AI agents"""

from .application.memory import add_memory, get_memory_by_id, graph_search, search_memories
from .version import __version__

__all__ = [
    "__version__",
    "add_memory",
    "search_memories",
    "graph_search",
    "get_memory_by_id",
]
