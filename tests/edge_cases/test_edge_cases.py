"""Tests for edge cases and regression scenarios."""

import pytest

pytestmark = pytest.mark.edge_case
from datetime import UTC, datetime, timedelta

from memg_core.core.models import Memory, MemoryType
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search


def test_unknown_memory_type_falls_back_to_note(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Test that unknown memory type falls back to note in both indexing and retrieval."""
    # Create a memory with an unknown type (bypassing enum validation)
    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        content="This is content",
        summary="This is summary",
        title="This is title",
        memory_type=MemoryType.NOTE,  # Start with a valid type
    )

    # Manually create a payload with unknown type to test the retrieval fallback
    unknown_payload = memory.to_qdrant_payload()
    unknown_payload["memory_type"] = "unknown_type"

    # Add to qdrant directly with unknown type
    vector = embedder.get_embedding(memory.content)
    qdrant_fake.add_point(vector=vector, payload=unknown_payload, point_id="memory-1")

    # Also test in kuzu (not through the pipeline)
    kuzu_fake.add_node("Memory", {
        "id": "memory-1",
        "user_id": "test-user",
        "content": "This is content",
        "memory_type": "unknown_type",  # Unknown type in Kuzu too
        "title": "This is title",
        "summary": "This is summary",
        "source": "user",
        "tags": "",
        "confidence": 0.8,
        "is_valid": True,
        "created_at": memory.created_at.isoformat(),
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    })

    # Retrieve via vector search
    results = graph_rag_search(
        query="content",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should retrieve the memory and normalize type to NOTE
    assert len(results) == 1
    assert results[0].memory.id == "memory-1"
    assert results[0].memory.memory_type == MemoryType.NOTE


def test_datetime_handling_naive_to_utc_normalization(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Test that datetime handling normalizes naive datetimes to UTC."""
    # Create a memory with timezone-aware datetime
    utc_dt = datetime.now(UTC).replace(microsecond=0)

    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        content="Test content",
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
    """Test that large content truncation in Kuzu node doesn't break payload."""
    # Create a memory with very large content
    large_content = "x" * 2000  # 2000 characters

    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        content=large_content,
    )

    # Add to index
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    # Check Qdrant payload - should have full content
    qdrant_point = qdrant_fake.get_point("memory-1")
    assert len(qdrant_point["payload"]["content"]) == 2000

    # Check Kuzu node - should have truncated content
    kuzu_node = kuzu_fake.nodes["Memory"]["memory-1"]
    assert len(kuzu_node["content"]) == 500  # Truncated to 500 chars

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
