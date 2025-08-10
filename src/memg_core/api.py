#!/usr/bin/env python3
"""Minimal public API for memg-core.

Simple functions for add/search operations that wrap the existing
graph-first retrieval and deterministic indexing infrastructure.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from memg_core.models.core import Memory, MemoryType, SearchResult


def add_note(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a note-type memory.

    Args:
        text: The note content
        user_id: User identifier for isolation
        title: Optional title
        tags: Optional list of tags

    Returns:
        The created Memory object
    """
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.NOTE,
        title=title,
        tags=tags or [],
    )

    # add_memory is sync and returns the memory ID
    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    # Update memory with the actual ID returned
    memory.id = memory_id
    return memory


def add_document(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a document-type memory.

    Args:
        text: The document content
        user_id: User identifier for isolation
        title: Optional title
        summary: Optional AI-generated summary (affects indexing)
        tags: Optional list of tags

    Returns:
        The created Memory object
    """
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.DOCUMENT,
        title=title,
        summary=summary,
        tags=tags or [],
    )

    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    memory.id = memory_id
    return memory


def add_task(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    due_date: datetime | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a task-type memory.

    Args:
        text: The task description
        user_id: User identifier for isolation
        title: Optional title (affects indexing when combined with content)
        due_date: Optional due date
        tags: Optional list of tags

    Returns:
        The created Memory object
    """
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.TASK,
        title=title,
        due_date=due_date,
        tags=tags or [],
    )

    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    memory.id = memory_id
    return memory


def search(
    query: str,
    *,
    user_id: str | None = None,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
) -> list[SearchResult]:
    """Search memories using GraphRAG (graph-first with vector fallback).

    Args:
        query: Search query string
        user_id: Optional user filter for isolation
        limit: Maximum number of results
        filters: Optional additional filters for vector search

    Returns:
        List of SearchResult objects, ranked by relevance
    """
    if not user_id:
        # If no user_id specified, we need to handle this case
        # For now, require user_id for proper isolation
        raise ValueError("user_id is required for search")

    from memg_core.processing.retrieval.graph_rag import graph_rag_search

    return asyncio.run(
        graph_rag_search(
            query=query,
            user_id=user_id,
            limit=limit,
            filters=filters or {},
        )
    )


# Async versions for direct use
async def add_note_async(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Async version of add_note."""
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.NOTE,
        title=title,
        tags=tags or [],
    )
    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    memory.id = memory_id
    return memory


async def add_document_async(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Async version of add_document."""
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.DOCUMENT,
        title=title,
        summary=summary,
        tags=tags or [],
    )
    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    memory.id = memory_id
    return memory


async def add_task_async(
    text: str,
    user_id: str,
    *,
    title: str | None = None,
    due_date: datetime | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Async version of add_task."""
    memory = Memory(
        user_id=user_id,
        content=text,
        memory_type=MemoryType.TASK,
        title=title,
        due_date=due_date,
        tags=tags or [],
    )
    from memg_core.application.memory import add_memory

    memory_id = add_memory(memory)
    memory.id = memory_id
    return memory


async def search_async(
    query: str,
    *,
    user_id: str | None = None,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
) -> list[SearchResult]:
    """Async version of search."""
    if not user_id:
        raise ValueError("user_id is required for search")

    from memg_core.processing.retrieval.graph_rag import graph_rag_search

    return await graph_rag_search(
        query=query,
        user_id=user_id,
        limit=limit,
        filters=filters or {},
    )
