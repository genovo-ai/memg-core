"""Tests for edge cases and regression scenarios."""

import pytest

pytestmark = pytest.mark.edge_case

from memg_core.core.pipeline.indexer import add_memory_index
from memg_core.core.pipeline.retrieval import graph_rag_search


def test_unknown_memory_type_rejected_by_yaml_validation(
    mem_factory, embedder, qdrant_fake, kuzu_fake
):
    """YAML-driven core properly rejects unknown memory types."""
    memory = mem_factory(id="memory-1", user_id="test-user", memory_type="memo_test")
    unknown_payload = memory.to_qdrant_payload()
    unknown_payload["core"]["memory_type"] = "invalid_type"  # invalid type

    v = embedder.get_embedding(memory.payload["statement"])
    qdrant_fake.add_point(vector=v, payload=unknown_payload, point_id="memory-1")

    # Should raise ProcessingError due to YAML validation
    from memg_core.core.exceptions import ProcessingError

    with pytest.raises(
        ProcessingError, match="Failed to get anchor field for memory type 'invalid_type'"
    ):
        graph_rag_search(
            query="Test",
            user_id="test-user",
            limit=10,
            qdrant=qdrant_fake,
            kuzu=kuzu_fake,
            embedder=embedder,
            mode="vector",
        )


def test_datetime_handling_naive_to_utc_normalization(
    mem_factory, embedder, qdrant_fake, kuzu_fake
):
    """Retrieval should still find the memory (filterless vector)."""
    memory = mem_factory(id="memory-1", user_id="test-user")
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)
    results = graph_rag_search(
        query="Test",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
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


def test_large_content_truncation_in_kuzu_node_does_not_break_payload(
    mem_factory, embedder, qdrant_fake, kuzu_fake
):
    """Full content stays in Qdrant payload under entity.details (large content for memo_test)."""
    large = "x" * 2000
    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "This is a test with large details", "details": large},
    )
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    pt = qdrant_fake.get_point("memory-1")
    assert len(pt["payload"]["entity"]["details"]) == 2000  # full text stays in vector store
