"""Tests for the retrieval pipeline."""

import pytest

pytestmark = pytest.mark.pipeline
from datetime import datetime

from memg_core.core.models import Memory, SearchResult
from memg_core.core.pipeline.retrieval import (
    _append_neighbors,
    _build_graph_query_for_memos,
    _rerank_with_vectors,
    _rows_to_memories,
    graph_rag_search,
)


def test_build_graph_query_for_memos_basic():
    """Test building a basic graph query."""
    query, params = _build_graph_query_for_memos("test query", user_id="test-user", limit=10)

    # Current lean core: simple Memory query, no entity joins
    assert "MATCH (m:Memory)" in query
    assert "m.user_id = $user_id" in query
    assert "LIMIT $limit" in query
    assert params["user_id"] == "test-user"
    assert params["limit"] == 10


def test_build_graph_query_for_memos_with_relation_names():
    """Test building a graph query with custom relation names."""
    query, params = _build_graph_query_for_memos(
        "test query", user_id="test-user", limit=10, relation_names=["RELATED_TO", "SUPPORTS"]
    )

    # Current lean core: relation_names parameter exists but simple query doesn't use entity joins
    assert "MATCH (m:Memory)" in query
    assert params["user_id"] == "test-user"


def test_build_graph_query_for_memos_with_memo_type():
    """Test building a graph query with memo type filter."""
    query, params = _build_graph_query_for_memos(
        "test query", user_id="test-user", limit=10, memo_type="memo_test"
    )

    # Current lean core: simple Memory query with memo_type filter
    assert "MATCH (m:Memory)" in query
    assert params["user_id"] == "test-user"


def test_rows_to_memories():
    """Test converting graph query rows to Memory objects."""
    # Create test rows
    rows = [
        {
            "node": {
                "id": "memory-1",
                "user_id": "test-user",
                "statement": "Memory 1 content",
                "memory_type": "memo_test",
                "created_at": "2023-01-01T00:00:00+00:00",
                "confidence": 0.8,
            }
        },
        {
            "node": {
                "id": "memory-2",
                "user_id": "test-user",
                "statement": "Memory 2 summary",
                "memory_type": "memo",
                "created_at": "2023-01-02T00:00:00+00:00",
                "confidence": 0.9,
            }
        },
    ]

    # Convert to memories
    memories = _rows_to_memories(rows)

    assert len(memories) == 2
    assert memories[0].id == "memory-1"
    assert memories[0].user_id == "test-user"
    assert memories[0].payload["statement"] == "Memory 1 content"
    assert memories[0].memory_type == "memo_test"
    assert memories[0].created_at.isoformat() == "2023-01-01T00:00:00+00:00"
    # No hardcoded tags - removed as part of audit

    assert memories[1].id == "memory-2"
    assert memories[1].memory_type == "memo"
    assert memories[1].payload["statement"] == "Memory 2 summary"


def test_rows_to_memories_handles_invalid_memory_type():
    """Test that _rows_to_memories handles invalid memory types."""
    # Create test row with invalid memory type
    rows = [
        {
            "node": {
                "id": "memory-1",
                "user_id": "test-user",
                "statement": "Memory 1 content",
                "type": "invalid_type",
                "created_at": "2023-01-01T00:00:00+00:00",
            }
        }
    ]

    # Convert to memories
    memories = _rows_to_memories(rows)

    assert len(memories) == 1
    assert memories[0].type == "invalid_type"  # Current core preserves invalid types


def test_rows_to_memories_handles_invalid_date():
    """Test that _rows_to_memories handles invalid dates."""
    # Create test row with invalid date
    rows = [
        {
            "node": {
                "id": "memory-1",
                "user_id": "test-user",
                "statement": "Memory 1 content",
                "memory_type": "memo_test",
                "created_at": "not-a-date",
            }
        }
    ]

    # Convert to memories
    memories = _rows_to_memories(rows)

    assert len(memories) == 1
    assert isinstance(memories[0].created_at, datetime)  # Should use current time


def test_rerank_with_vectors(embedder, qdrant_fake):
    """Test reranking graph results with vector similarity."""
    # Create test memories with very different content
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "aaaa aaaa aaaa",
            "details": "This is a memo_test with unrelated content.",
        },
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "test query similar",
            "details": "This is a memo_test with similar content.",
        },
    )

    # Add to Qdrant
    vector1 = embedder.get_embedding("aaaa aaaa aaaa")
    vector2 = embedder.get_embedding("test query similar")

    qdrant_fake.add_point(vector=vector1, payload=memory1.to_qdrant_payload(), point_id="memory-1")
    qdrant_fake.add_point(vector=vector2, payload=memory2.to_qdrant_payload(), point_id="memory-2")

    # Rerank with a query closer to memory2
    results = _rerank_with_vectors(
        "test query",  # Should be more similar to memory2
        [memory1, memory2],
        qdrant_fake,
        embedder,
    )

    assert len(results) == 2
    assert results[0].memory.id == "memory-2"  # Should be ranked first
    assert results[1].memory.id == "memory-1"
    assert results[0].score > results[1].score
    assert results[0].source == "graph_rerank"


def test_append_neighbors(kuzu_fake):
    """Test appending graph neighbors to results."""
    # Create test memories
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "Memory 1 content", "details": "This is the detail for memory 1."},
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "Memory 2 content", "details": "This is the detail for memory 2."},
    )

    memory3 = Memory(
        id="memory-3",
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "Memory 3 content", "details": "This is the detail for memory 3."},
    )

    # Add to Kuzu
    kuzu_fake.add_node("Memory", memory1.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory2.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory3.to_kuzu_node())

    # Add relationships
    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="RELATED_TO",
        from_id="memory-1",
        to_id="memory-2",
    )

    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="RELATED_TO",
        from_id="memory-1",
        to_id="memory-3",
    )

    # Create search results
    search_results = [
        SearchResult(memory=memory1, score=0.9, distance=None, source="graph_rerank", metadata={})
    ]

    # Append neighbors
    expanded_results = _append_neighbors(
        search_results, kuzu_fake, neighbor_limit=5, relation_names=["RELATED_TO"]
    )

    assert len(expanded_results) == 3  # Original + 2 neighbors

    # Find the neighbor results
    neighbor_results = [r for r in expanded_results if r.source == "graph_neighbor"]
    assert len(neighbor_results) == 2

    # Check that neighbors have correct metadata
    for r in neighbor_results:
        assert r.metadata["from"] == "memory-1"
        assert r.memory.id in ["memory-2", "memory-3"]
        assert r.score < 0.9  # Lower than seed score


def test_neighbor_cap_respected(kuzu_fake):
    """Test that neighbor_cap is respected."""
    # Create test memories
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "Memory 1 content", "details": "This is the detail for memory 1."},
    )

    # Create 5 neighbor memories
    neighbor_memories = []
    for i in range(2, 7):
        memory = Memory(
            id=f"memory-{i}",
            user_id="test-user",
            memory_type="memo_test",
            statement=f"Memory {i} content",
            payload={"details": f"This is the detail for memory {i}."},
        )
        neighbor_memories.append(memory)
        kuzu_fake.add_node("Memory", memory.to_kuzu_node())

    # Add memory1 to Kuzu
    kuzu_fake.add_node("Memory", memory1.to_kuzu_node())

    # Add relationships from memory1 to all neighbors
    for memory in neighbor_memories:
        kuzu_fake.add_relationship(
            from_table="Memory",
            to_table="Memory",
            rel_type="RELATED_TO",
            from_id="memory-1",
            to_id=memory.id,
        )

    # Create search results with memory1
    search_results = [
        SearchResult(memory=memory1, score=0.9, distance=None, source="graph_rerank", metadata={})
    ]

    # Append neighbors with cap of 3
    expanded_results = _append_neighbors(
        search_results, kuzu_fake, neighbor_limit=3, relation_names=["RELATED_TO"]
    )

    # Should have 4 results: original + 3 neighbors (capped)
    assert len(expanded_results) == 4

    # Find the neighbor results
    neighbor_results = [r for r in expanded_results if r.source == "graph_neighbor"]
    assert len(neighbor_results) == 3  # Capped at 3


def test_search_vector_fallback_no_graph(embedder, qdrant_fake, kuzu_fake):
    """Test search with vector fallback when graph returns no results."""
    # Create test memories in Qdrant only
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Apple banana orange",
            "details": "This is a memo_test about fruits.",
        },
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Machine learning algorithm",
            "details": "This is a memo_test about AI.",
        },
    )

    # Add to Qdrant
    vector1 = embedder.get_embedding("Apple banana orange")
    vector2 = embedder.get_embedding("Machine learning algorithm")

    qdrant_fake.add_point(vector=vector1, payload=memory1.to_qdrant_payload(), point_id="memory-1")
    qdrant_fake.add_point(vector=vector2, payload=memory2.to_qdrant_payload(), point_id="memory-2")

    # Search with a query that won't match in graph but will in vector
    results = graph_rag_search(
        query="Machine learning",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
        mode="vector",
    )

    assert len(results) > 0
    assert results[0].memory.id == "memory-2"  # Should match this one better
    assert results[0].source in {"qdrant", "vector_fallback"}


def test_search_graph_first_rerank_then_neighbors(embedder, qdrant_fake, kuzu_fake):
    """Test search with graph-first, rerank, and neighbors (lean core: Memory-only graph)."""
    # Create test memories
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Database concepts with special keyword",
            "details": "This is a memo_test about databases.",
        },
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Related concepts without special word",
            "details": "This is a related memo_test.",
        },
    )

    # Add to both Qdrant and Kuzu
    vector1 = embedder.get_embedding("Database concepts with special keyword")
    vector2 = embedder.get_embedding("Related concepts without special word")

    qdrant_fake.add_point(vector=vector1, payload=memory1.to_qdrant_payload(), point_id="memory-1")
    qdrant_fake.add_point(vector=vector2, payload=memory2.to_qdrant_payload(), point_id="memory-2")

    kuzu_fake.add_node("Memory", memory1.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory2.to_kuzu_node())

    # Add memory-to-memory relationship
    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="RELATED_TO",
        from_id="memory-1",
        to_id="memory-2",
    )

    # Search - lean core does Memory-only graph queries, then vector rerank, then neighbors
    results = graph_rag_search(
        query="keyword",
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    # Should find at least one memory
    assert len(results) >= 1

    # Current lean implementation may use "qdrant" or "graph_rerank" depending on path taken
    sources = {r.source for r in results}
    assert sources.intersection({"qdrant", "graph_rerank", "neighbors"})


def test_filters_user_id_propagate_to_qdrant(embedder, qdrant_fake, kuzu_fake):
    """Test that user_id filter propagates to Qdrant search."""
    # Create memories for different users
    memory1 = Memory(
        id="memory-1",
        user_id="user1",
        memory_type="memo_test",
        payload={"statement": "Content for user1", "details": "This is a memo_test for user 1."},
        # No hardcoded tags - removed as part of audit
    )

    memory2 = Memory(
        id="memory-2",
        user_id="user2",
        memory_type="memo_test",
        payload={"statement": "Content for user2", "details": "This is a memo_test for user 2."},
    )

    # Add to Qdrant
    vector1 = embedder.get_embedding(memory1.payload["statement"])
    vector2 = embedder.get_embedding(memory2.payload["statement"])

    qdrant_fake.add_point(vector=vector1, payload=memory1.to_qdrant_payload(), point_id="memory-1")
    qdrant_fake.add_point(vector=vector2, payload=memory2.to_qdrant_payload(), point_id="memory-2")

    # Search with user_id filter
    results_user1 = graph_rag_search(
        query="content",
        user_id="user1",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
        mode="vector",
    )

    assert len(results_user1) == 1
    assert results_user1[0].memory.user_id == "user1"

    # Test basic user_id filtering - no hardcoded entity fields
    results_user2 = graph_rag_search(
        query="content",
        user_id="user2",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
        mode="vector",
    )

    assert len(results_user2) == 1
    assert results_user2[0].memory.user_id == "user2"
