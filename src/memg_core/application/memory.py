#!/usr/bin/env python3
"""Thin application orchestration for core memory flows.

Provides add and search functions over the core services:
- Deterministic indexing policy
- Embedding generation
- Qdrant payload upsert with index_text
- Kuzu graph writes
- Graph-first retrieval with vector rerank and neighbor append
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from memg_core.core_services.embeddings import GenAIEmbedder
from memg_core.database_services import KuzuInterface, QdrantInterface
from memg_core.models.core import Memory
from memg_core.processing.ingestion import add_memory_index
from memg_core.processing.retrieval.graph_rag import graph_rag_search


def add_memory(
    memory: Memory,
    *,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
    embedder: GenAIEmbedder | None = None,
    collection: str | None = None,
) -> str:
    """Add a memory across vector and graph stores and return its id.

    Steps:
    - compute index_text per policy
    - embed index_text
    - upsert Qdrant payload including index_text
    - create Memory node in Kuzu
    """
    qdrant = qdrant or QdrantInterface()
    kuzu = kuzu or KuzuInterface()
    embedder = embedder or GenAIEmbedder()

    # Delegate to ingestion indexer to avoid duplication
    return add_memory_index(
        memory,
        qdrant=qdrant,
        kuzu=kuzu,
        embedder=embedder,
        collection=collection,
    )


async def search_memories(
    query: str,
    user_id: str,
    *,
    limit: int = 10,
    filters: dict | None = None,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
    embedder: GenAIEmbedder | None = None,
) -> list[Any]:
    """Graph-first search with vector rerank and neighbor append; vector fallback."""
    return await graph_rag_search(
        query=query,
        user_id=user_id,
        limit=limit,
        filters=filters or {},
        qdrant=qdrant,
        kuzu=kuzu,
        embedder=embedder,
    )


async def graph_search(
    query: str,
    *,
    entity_types: Iterable[str] | None = None,
    user_id: str | None = None,
    limit: int = 10,
    kuzu: KuzuInterface | None = None,
) -> list[Any]:
    from memg_core.processing.memory_retriever import MemoryRetriever

    retriever = MemoryRetriever(kuzu_interface=kuzu)
    return await retriever.graph_search(
        query=query, entity_types=list(entity_types or []), limit=limit, user_id=user_id
    )


async def get_memory_by_id(
    memory_id: str, *, qdrant: QdrantInterface | None = None
) -> Memory | None:
    from memg_core.processing.memory_retriever import MemoryRetriever

    retriever = MemoryRetriever(qdrant_interface=qdrant)
    return await retriever.get_memory_by_id(memory_id)


def update_memory(
    memory: Memory,
    *,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
    embedder: GenAIEmbedder | None = None,
    collection: str | None = None,
) -> str:
    """Update an existing memory (replaces content and re-computes embedding)."""
    from datetime import UTC, datetime

    from memg_core.processing.ingestion import add_memory_index

    # Update timestamp
    memory.created_at = datetime.now(UTC)

    return add_memory_index(
        memory,
        qdrant=qdrant,
        kuzu=kuzu,
        embedder=embedder,
        collection=collection,
    )


def delete_memory(
    memory_id: str,
    *,
    qdrant: QdrantInterface | None = None,
    kuzu: KuzuInterface | None = None,
) -> None:
    """Delete a memory from both Qdrant and Kuzu."""
    qdrant = qdrant or QdrantInterface()
    kuzu = kuzu or KuzuInterface()

    # Remove from Qdrant
    from qdrant_client.models import PointIdsList

    qdrant.client.delete(
        collection_name=qdrant.collection_name, points_selector=PointIdsList(points=[memory_id])
    )

    # Remove from Kuzu
    kuzu.query("MATCH (m:Memory {id: $id}) DELETE m", {"id": memory_id})
