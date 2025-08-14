"""DEPRECATED - Indexing logic moved to YAML translator"""

from __future__ import annotations

from .models import Memory


def build_index_text(memory: Memory) -> str:
    """DEPRECATED: Use YAML translator build_anchor_text instead.

    This function is kept for backward compatibility but will be removed.
    All indexing should use the YAML-defined anchor field strategy.
    """
    # Fallback: try to get any text from payload
    if "content" in memory.payload:
        return str(memory.payload["content"])
    if "summary" in memory.payload:
        return str(memory.payload["summary"])

    # Last resort
    return f"Memory {memory.id}"
