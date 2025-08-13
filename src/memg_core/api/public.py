"""Minimal public API for memory system - 4 sync functions only"""

from __future__ import annotations

from datetime import datetime
import os
from typing import Any

from ..core.config import get_config
from ..core.exceptions import ValidationError
from ..core.interfaces.embedder import Embedder
from ..core.interfaces.kuzu import KuzuInterface
from ..core.interfaces.qdrant import QdrantInterface
from ..core.models import Memory, MemoryType, SearchResult
from ..core.pipeline.indexer import add_memory_index
from ..core.pipeline.retrieval import graph_rag_search


def _index_memory_with_optional_yaml(memory: Memory) -> str:
    """Helper to index a memory with optional YAML plugin support"""
    # Initialize interfaces with explicit paths from config
    config = get_config()

    # Get storage paths from environment (API layer responsibility)
    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    # Check if YAML plugin should provide index text override
    index_text_override = None
    if os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() == "true":
        try:
            from ..plugins.yaml_schema import build_index_text_with_yaml

            index_text_override = build_index_text_with_yaml(memory)
        except ImportError:
            # Plugin is optional, continue without it
            pass

    # Index the memory
    return add_memory_index(memory, qdrant, kuzu, embedder, index_text_override=index_text_override)


def add_note(
    text: str,
    user_id: str,
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
    if not text or not text.strip():
        raise ValidationError("Note content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    memory = Memory(
        user_id=user_id,
        content=text.strip(),
        memory_type=MemoryType.NOTE,
        title=title,
        summary=None,
        source="user",
        confidence=0.8,
        vector=None,
        is_valid=True,
        expires_at=None,
        supersedes=None,
        superseded_by=None,
        task_status=None,
        task_priority=None,
        assignee=None,
        due_date=None,
        tags=tags or [],
    )

    memory.id = _index_memory_with_optional_yaml(memory)
    return memory


def add_document(
    text: str,
    user_id: str,
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
    if not text or not text.strip():
        raise ValidationError("Document content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    memory = Memory(
        user_id=user_id,
        content=text.strip(),
        memory_type=MemoryType.DOCUMENT,
        title=title,
        summary=summary,
        source="user",
        confidence=0.8,
        vector=None,
        is_valid=True,
        expires_at=None,
        supersedes=None,
        superseded_by=None,
        task_status=None,
        task_priority=None,
        assignee=None,
        due_date=None,
        tags=tags or [],
    )

    memory.id = _index_memory_with_optional_yaml(memory)
    return memory


def add_task(
    text: str,
    user_id: str,
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
    if not text or not text.strip():
        raise ValidationError("Task content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    memory = Memory(
        user_id=user_id,
        content=text.strip(),
        memory_type=MemoryType.TASK,
        title=title,
        summary=None,
        source="user",
        confidence=0.8,
        vector=None,
        is_valid=True,
        expires_at=None,
        supersedes=None,
        superseded_by=None,
        task_status=None,
        task_priority=None,
        assignee=None,
        due_date=due_date,
        tags=tags or [],
    )

    memory.id = _index_memory_with_optional_yaml(memory)
    return memory


def search(
    query: str,
    user_id: str,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
) -> list[SearchResult]:
    """Search memories using GraphRAG (graph-first with vector fallback).

    Args:
        query: Search query string
        user_id: User ID for filtering (required)
        limit: Maximum number of results
        filters: Optional additional filters for vector search

    Returns:
        List of SearchResult objects, ranked by relevance
    """
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required for search")

    # Initialize interfaces with explicit paths from config
    config = get_config()

    # Get storage paths from environment (API layer responsibility)
    qdrant_path = os.getenv("QDRANT_STORAGE_PATH")
    kuzu_path = os.getenv("KUZU_DB_PATH", config.memg.kuzu_database_path)

    qdrant = QdrantInterface(
        collection_name=config.memg.qdrant_collection_name, storage_path=qdrant_path
    )
    kuzu = KuzuInterface(db_path=kuzu_path)
    embedder = Embedder()

    # Check if YAML schema is enabled to pass relation names
    relation_names = None
    if os.getenv("MEMG_ENABLE_YAML_SCHEMA", "false").lower() == "true":
        try:
            from ..plugins.yaml_schema import get_relation_names

            relation_names = get_relation_names()
        except ImportError:
            # Plugin is optional, continue without it
            relation_names = None

    # Read neighbor cap here (API layer)
    neighbor_cap = int(os.getenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "5"))

    # Perform search
    return graph_rag_search(
        query=query.strip(),
        user_id=user_id,
        limit=limit,
        qdrant=qdrant,
        kuzu=kuzu,
        embedder=embedder,
        filters=filters,
        relation_names=relation_names,
        neighbor_cap=neighbor_cap,
    )
