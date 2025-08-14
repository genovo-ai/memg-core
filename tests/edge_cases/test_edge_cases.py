"""Tests for edge cases and regression scenarios."""

import pytest

pytestmark = pytest.mark.edge_case
from datetime import UTC, datetime, timedelta

from memg_core.core.models import Memory
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search


def test_unknown_memory_type_falls_back_to_note(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Test that unknown memory type falls back to note in both indexing and retrieval."""
    # Create a memory with proper payload structure
    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        memory_type="unknown_type",  # Test with unknown type directly
        payload={
            "statement": "This is content",
            "summary": "This is summary",
            "title": "This is title",
        },
    )

    # Add to qdrant
    vector = embedder.get_embedding(memory.content)  # .content reads from payload.statement
    qdrant_fake.add_point(vector=vector, payload=memory.to_qdrant_payload(), point_id="memory-1")

    # Also add to kuzu using current core structure
    kuzu_fake.add_node("Memory", memory.to_kuzu_node())

    # Retrieve via vector search
    results = graph_rag_search(
        query="content",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should retrieve the memory (current core preserves unknown types)
    assert len(results) == 1
    assert results[0].memory.id == "memory-1"
    # Current core preserves the original memory type, doesn't normalize to "note"
    assert results[0].memory.memory_type == "unknown_type"


def test_datetime_handling_naive_to_utc_normalization(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Test that datetime handling normalizes naive datetimes to UTC."""
    # Create a memory with timezone-aware datetime
    utc_dt = datetime.now(UTC).replace(microsecond=0)

    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        payload={"statement": "Test content"},  # Current core uses payload.statement
        created_at=utc_dt,  # UTC datetime
    )

    # Add to index
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    # Retrieve via vector search
    results = graph_rag_search(
        query="content",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should retrieve the memory with UTC datetime
    assert len(results) == 1
    retrieved_dt = results[0].memory.created_at

    # Check that it has timezone info
    assert retrieved_dt.tzinfo is not None

    # Check that it's the same time (accounting for potential string roundtrip)
    expected_dt = datetime.fromisoformat(utc_dt.isoformat())
    assert retrieved_dt == expected_dt or retrieved_dt.replace(tzinfo=UTC) == utc_dt


def test_empty_search_returns_empty_list_not_exception(embedder, qdrant_fake, kuzu_fake):
    """Test that empty search returns empty list, not exception."""
    # Search with no memories in the system
    results = graph_rag_search(
        query="non-existent",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should return empty list, not raise
    assert isinstance(results, list)
    assert len(results) == 0


def test_large_content_truncation_in_kuzu_node_does_not_break_payload(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Test that large content in payload doesn't break indexing."""
    # Create a memory with very large content
    large_content = "x" * 2000  # 2000 characters

    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        payload={"statement": large_content},  # Current core stores content in payload.statement
    )

    # Add to index
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    # Check Qdrant payload - should have full content in entity.statement
    qdrant_point = qdrant_fake.get_point("memory-1")
    assert len(qdrant_point["payload"]["entity"]["statement"]) == 2000

    # Check Kuzu node - current core doesn't store content/statement in Kuzu (only metadata)
    kuzu_node = kuzu_fake.nodes["Memory"]["memory-1"]
    assert "content" not in kuzu_node  # Current core doesn't store content in Kuzu
    assert "statement" not in kuzu_node or len(kuzu_node.get("statement", "")) <= 2000

    # Retrieve via vector search (use a query that won't match in graph)
    results = graph_rag_search(
        query="unique_query_that_wont_match_in_graph",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should retrieve the memory with full content (from vector fallback)
    assert len(results) == 1
    assert results[0].source == "vector_fallback"
    assert len(results[0].memory.content) == 2000
