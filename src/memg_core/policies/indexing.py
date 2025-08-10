#!/usr/bin/env python3
"""Deterministic indexing policy for memg-core.

Selects the `index_text` used for embeddings and persists it in vector payloads.
"""

from __future__ import annotations

from memg_core.models.core import Memory, MemoryType


def _safe_join_title_and_content(title: str | None, content: str) -> str:
    if title and title.strip():
        return f"{title.strip()}. {content}".strip()
    return content


def build_index_text(memory: Memory) -> str:
    """Return the deterministic index_text for a memory based on its type.

    - note: content
    - document: summary if present else content
    - task: content (+ title if present)
    """
    if memory.memory_type == MemoryType.NOTE:
        return memory.content
    if memory.memory_type == MemoryType.DOCUMENT:
        return memory.summary if (memory.summary and memory.summary.strip()) else memory.content
    if memory.memory_type == MemoryType.TASK:
        return _safe_join_title_and_content(memory.title, memory.content)
    # Fallback for unknown types: use content
    return memory.content
