"""Tests for edge cases and regression scenarios."""

import pytest

pytestmark = pytest.mark.edge_case
from datetime import UTC, datetime, timedelta

from memg_core.core.models import Memory
from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search


def test_unknown_memory_type_falls_back_to_note(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Current core preserves the literal memory_type (no enum coercion)."""
    memory = mem_factory(id="memory-1", user_id="test-user", memory_type="note")
    unknown_payload = memory.to_qdrant_payload()
    unknown_payload["core"]["memory_type"] = "invalid_type"  # preserve as-is

    v = embedder.get_embedding(memory.content)
    qdrant_fake.add_point(vector=v, payload=unknown_payload, point_id="memory-1")

    results = graph_rag_search(
        query="Test", user_id="test-user", limit=10, qdrant=qdrant_fake, kuzu=kuzu_fake, embedder=embedder
    )
    assert len(results) == 1
    assert results[0].memory.memory_type == "invalid_type"


def test_datetime_handling_naive_to_utc_normalization(mem_factory, embedder, qdrant_fake, kuzu_fake):
    """Retrieval should still find the memory (filterless vector)."""
    memory = mem_factory(id="memory-1", user_id="test-user")
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)
    results = graph_rag_search(
        query="Test", user_id="test-user", limit=10, qdrant=qdrant_fake, kuzu=kuzu_fake, embedder=embedder
    )
    assert len(results) == 1


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
    """Full content stays in Qdrant payload under entity.content (anchor for notes)."""
    large = "x" * 2000
    memory = Memory(id="memory-1", user_id="test-user", memory_type="note", payload={"content": large})
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    pt = qdrant_fake.get_point("memory-1")
    assert len(pt["payload"]["entity"]["content"]) == 2000  # full text stays in vector store
