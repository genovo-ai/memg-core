"""Deterministic indexing policy for memory system"""

from __future__ import annotations

from .models import Memory, MemoryType


def _safe_join_title_and_content(title: str | None, content: str) -> str:
    """Safely join title and content with period separator"""
    if title and title.strip():
        return f"{title.strip()}. {content}".strip()
    return content


def build_index_text(memory: Memory) -> str:
    """Return the deterministic index_text for a memory based on its type.

    Args:
        memory: The memory to build index text for

    Default behavior (deterministic only):
    - note: content
    - document: summary if present else content
    - task: content (+ title if present)
    """
    # Default deterministic behavior
    if memory.memory_type == MemoryType.NOTE:
        return memory.content
    if memory.memory_type == MemoryType.DOCUMENT:
        return memory.summary if (memory.summary and memory.summary.strip()) else memory.content
    if memory.memory_type == MemoryType.TASK:
        return _safe_join_title_and_content(memory.title, memory.content)
    # Fallback for unknown types: use content
    return memory.content
