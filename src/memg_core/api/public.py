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
from ..core.models import Memory, SearchResult
from ..core.pipeline.indexer import add_memory_index
from ..core.pipeline.retrieval import graph_rag_search
from ..core.yaml_translator import build_anchor_text, create_memory_from_yaml


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

    # Use YAML translator for anchor text if schema is available
    import contextlib

    index_text_override = None
    with contextlib.suppress(Exception):
        index_text_override = build_anchor_text(memory)

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

    payload = {
        "content": text.strip(),
        "source": "user",
    }
    if title:
        payload["title"] = title

    return add_memory("note", payload, user_id, tags)


def add_document(
    text: str,
    user_id: str,
    title: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a document-type memory.

    Args:
        text: The document content (stored as 'body' in new schema)
        user_id: User identifier for isolation
        title: Optional title
        summary: Optional AI-generated summary (used as anchor for embedding)
        tags: Optional list of tags

    Returns:
        The created Memory object
    """
    if not text or not text.strip():
        raise ValidationError("Document content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    payload = {
        "body": text.strip(),  # Note: 'body' not 'content' in new schema
        "source": "user",
    }
    if title:
        payload["title"] = title
    if summary:
        payload["summary"] = summary
    else:
        # Generate a basic summary from the first part of the document
        payload["summary"] = text.strip()[:200] + "..." if len(text.strip()) > 200 else text.strip()

    return add_memory("document", payload, user_id, tags)


def add_task(
    text: str,
    user_id: str,
    title: str | None = None,
    due_date: datetime | None = None,
    tags: list[str] | None = None,
) -> Memory:
    """Add a task-type memory.

    Args:
        text: The task description (used as summary in Jira-style)
        user_id: User identifier for isolation
        title: Optional title
        due_date: Optional due date
        tags: Optional list of tags

    Returns:
        The created Memory object
    """
    if not text or not text.strip():
        raise ValidationError("Task content cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")

    payload = {
        "summary": text.strip(),  # Jira-style: text becomes the summary (anchor)
        "source": "user",
        "task_status": "todo",  # Default status
        "task_priority": "medium",  # Default priority
    }
    if title:
        payload["title"] = title
    if due_date:
        payload["due_date"] = due_date

    return add_memory("task", payload, user_id, tags)


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


def add_memory(
    memory_type: str,
    payload: dict[str, Any],
    user_id: str,
    tags: list[str] | None = None,
) -> Memory:
    """Add a memory using YAML-defined entity type and payload.

    This is the generic memory creation function that validates against
    YAML schema and creates Memory objects from arbitrary entity types.

    Args:
        memory_type: Entity type name (e.g., "note", "document", "task")
        payload: Dictionary of field values for the entity
        user_id: User identifier for isolation
        tags: Optional list of tags to add

    Returns:
        The created Memory object

    Raises:
        ValidationError: If payload is invalid for the entity type
    """
    if not memory_type or not memory_type.strip():
        raise ValidationError("Memory type cannot be empty")
    if not user_id:
        raise ValidationError("User ID is required")
    if not payload:
        raise ValidationError("Payload cannot be empty")

    # Add tags to payload if provided
    if tags:
        payload = dict(payload)  # Don't modify original
        existing_tags = payload.get("tags", [])
        payload["tags"] = list(set(existing_tags + tags))

    # Create memory using YAML translator
    memory = create_memory_from_yaml(memory_type.strip(), payload, user_id)

    # Index the memory
    memory.id = _index_memory_with_optional_yaml(memory)
    return memory
