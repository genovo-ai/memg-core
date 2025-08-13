"""Tests for the retrieval pipeline."""

import pytest

pytestmark = pytest.mark.pipeline
from datetime import UTC, datetime

from memg_core.core.models import Memory, MemoryType, SearchResult
from memg_core.core.pipeline.retrieval import (
    _build_graph_query,
    _rows_to_memories,
    _rerank_with_vectors,
    _append_neighbors,
    graph_rag_search,
)


def test_build_graph_query_basic():
    """Test building a basic graph query."""
    query, params = _build_graph_query("test query", user_id="test-user", limit=10)

    assert "MATCH (m:Memory)-[r:MENTIONS]->(e:Entity)" in query
    assert "WHERE toLower(e.name) CONTAINS toLower($q)" in query
    assert "AND m.user_id = $user_id" in query
    assert "LIMIT $limit" in query
    assert params["q"] == "test query"
    assert params["user_id"] == "test-user"
    assert params["limit"] == 10


def test_build_graph_query_with_relation_names():
    """Test building a graph query with custom relation names."""
    query, params = _build_graph_query(
        "test query",
        user_id="test-user",
        limit=10,
        relation_names=["REFERENCES", "CONTAINS"]
    )

    assert "MATCH (m:Memory)-[r:REFERENCES|CONTAINS]->(e:Entity)" in query
    assert params["q"] == "test query"


def test_build_graph_query_with_entity_types():
    """Test building a graph query with entity type filters."""
    query, params = _build_graph_query(
        "test query",
        user_id="test-user",
        limit=10,
        entity_types=["PERSON", "ORGANIZATION"]
    )

    assert "AND (e.type = 'PERSON' OR e.type = 'ORGANIZATION')" in query
    assert params["q"] == "test query"


def test_rows_to_memories():
    """Test converting graph query rows to Memory objects."""
    # Create test rows
    rows = [
        {
            "m.id": "memory-1",
            "m.user_id": "test-user",
            "m.content": "Memory 1 content",
            "m.title": "Memory 1",
            "m.memory_type": "note",
            "m.created_at": "2023-01-01T00:00:00+00:00",
            "m.summary": None,
            "m.source": "user",
            "m.tags": "tag1,tag2",
            "m.confidence": 0.8,
        },
        {
            "m.id": "memory-2",
            "m.user_id": "test-user",
            "m.content": "Memory 2 content",
            "m.title": "Memory 2",
            "m.memory_type": "document",
            "m.created_at": "2023-01-02T00:00:00+00:00",
            "m.summary": "Memory 2 summary",
            "m.source": "user",
            "m.tags": "tag2,tag3",
            "m.confidence": 0.9,
        }
    ]

    # Convert to memories
    memories = _rows_to_memories(rows)

    assert len(memories) == 2
    assert memories[0].id == "memory-1"
    assert memories[0].user_id == "test-user"
    assert memories[0].content == "Memory 1 content"
    assert memories[0].title == "Memory 1"
    assert memories[0].memory_type == MemoryType.NOTE
    assert memories[0].created_at.isoformat() == "2023-01-01T00:00:00+00:00"
    assert memories[0].tags == ["tag1", "tag2"]

    assert memories[1].id == "memory-2"
    assert memories[1].memory_type == MemoryType.DOCUMENT
    assert memories[1].summary == "Memory 2 summary"


def test_rows_to_memories_handles_invalid_memory_type():
    """Test that _rows_to_memories handles invalid memory types."""
    # Create test row with invalid memory type
    rows = [
        {
            "m.id": "memory-1",
            "m.user_id": "test-user",
            "m.content": "Memory 1 content",
            "m.memory_type": "invalid_type",
            "m.created_at": "2023-01-01T00:00:00+00:00",
        }
    ]

    # Convert to memories
    memories = _rows_to_memories(rows)

    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.NOTE  # Should default to NOTE


def test_rows_to_memories_handles_invalid_date():
    """Test that _rows_to_memories handles invalid dates."""
    # Create test row with invalid date
    rows = [
        {
            "m.id": "memory-1",
            "m.user_id": "test-user",
            "m.content": "Memory 1 content",
            "m.memory_type": "note",
            "m.created_at": "not-a-date",
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
        content="aaaa aaaa aaaa",  # Very different from query
        memory_type=MemoryType.NOTE,
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        content="test query similar",  # More similar to query
        memory_type=MemoryType.NOTE,
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
        embedder
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
        content="Memory 1 content",
        memory_type=MemoryType.NOTE,
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        content="Memory 2 content",
        memory_type=MemoryType.NOTE,
    )

    memory3 = Memory(
        id="memory-3",
        user_id="test-user",
        content="Memory 3 content",
        memory_type=MemoryType.NOTE,
    )

    # Add to Kuzu
    kuzu_fake.add_node("Memory", memory1.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory2.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory3.to_kuzu_node())

    # Add relationships
    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="REFERENCES",
        from_id="memory-1",
        to_id="memory-2",
    )

    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="REFERENCES",
        from_id="memory-1",
        to_id="memory-3",
    )

    # Create search results
    search_results = [
        SearchResult(
            memory=memory1,
            score=0.9,
            distance=None,
            source="graph_rerank",
            metadata={}
        )
    ]

    # Append neighbors
    expanded_results = _append_neighbors(search_results, kuzu_fake, neighbor_limit=5)

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
        content="Memory 1 content",
        memory_type=MemoryType.NOTE,
    )

    # Create 5 neighbor memories
    neighbor_memories = []
    for i in range(2, 7):
        memory = Memory(
            id=f"memory-{i}",
            user_id="test-user",
            content=f"Memory {i} content",
            memory_type=MemoryType.NOTE,
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
            rel_type="REFERENCES",
            from_id="memory-1",
            to_id=memory.id,
        )

    # Create search results with memory1
    search_results = [
        SearchResult(
            memory=memory1,
            score=0.9,
            distance=None,
            source="graph_rerank",
            metadata={}
        )
    ]

    # Append neighbors with cap of 3
    expanded_results = _append_neighbors(search_results, kuzu_fake, neighbor_limit=3)

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
        content="Apple banana orange",
        memory_type=MemoryType.NOTE,
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        content="Machine learning algorithm",
        memory_type=MemoryType.NOTE,
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
    )

    assert len(results) > 0
    assert results[0].memory.id == "memory-2"  # Should match this one better
    assert results[0].source == "vector_fallback"


def test_search_graph_first_rerank_then_neighbors(embedder, qdrant_fake, kuzu_fake):
    """Test search with graph-first, rerank, and neighbors."""
    # Create test memories
    memory1 = Memory(
        id="memory-1",
        user_id="test-user",
        content="Database concepts with special keyword",  # Only this will match entity
        memory_type=MemoryType.NOTE,
    )

    memory2 = Memory(
        id="memory-2",
        user_id="test-user",
        content="Related concepts without special word",  # This won't match initially
        memory_type=MemoryType.NOTE,
    )

    # Add to both Qdrant and Kuzu
    vector1 = embedder.get_embedding("Database concepts with special keyword")
    vector2 = embedder.get_embedding("Related concepts without special word")

    qdrant_fake.add_point(vector=vector1, payload=memory1.to_qdrant_payload(), point_id="memory-1")
    qdrant_fake.add_point(vector=vector2, payload=memory2.to_qdrant_payload(), point_id="memory-2")

    kuzu_fake.add_node("Memory", memory1.to_kuzu_node())
    kuzu_fake.add_node("Memory", memory2.to_kuzu_node())

    # Create an entity node
    entity = {
        "id": "entity-1",
        "user_id": "test-user",
        "name": "keyword",  # Only memory1 contains this word
        "type": "CONCEPT",
        "description": "Special keyword concept",
        "confidence": 0.9,
        "created_at": "2023-01-01T00:00:00+00:00",
        "is_valid": True,
        "source_memory_id": "memory-1",
    }
    kuzu_fake.add_node("Entity", entity)

    # Add relationships
    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Entity",
        rel_type="MENTIONS",
        from_id="memory-1",
        to_id="entity-1",
    )

    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="REFERENCES",
        from_id="memory-1",
        to_id="memory-2",
    )

    # Search with a query that should match in graph
    results = graph_rag_search(
        query="keyword",  # Should match entity and find memory1, then neighbors
        user_id="test-user",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
    )

    assert len(results) == 2

    # First result should be from graph_rerank
    assert any(r.source == "graph_rerank" for r in results)

    # Second result should be from graph_neighbor
    assert any(r.source == "graph_neighbor" for r in results)


def test_filters_user_id_and_tags_propagate_to_qdrant(embedder, qdrant_fake, kuzu_fake):
    """Test that filters and user_id propagate to Qdrant search."""
    # Create memories for different users with different tags
    memory1 = Memory(
        id="memory-1",
        user_id="user1",
        content="Content for user1",
        memory_type=MemoryType.NOTE,
        tags=["tag1", "tag2"],
    )

    memory2 = Memory(
        id="memory-2",
        user_id="user2",
        content="Content for user2",
        memory_type=MemoryType.NOTE,
        tags=["tag2", "tag3"],
    )

    # Add to Qdrant
    vector1 = embedder.get_embedding(memory1.content)
    vector2 = embedder.get_embedding(memory2.content)

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
    )

    assert len(results_user1) == 1
    assert results_user1[0].memory.user_id == "user1"

    # Search with user_id and tags filter
    results_user2_tag3 = graph_rag_search(
        query="content",
        user_id="user2",
        limit=10,
        qdrant=qdrant_fake,
        kuzu=kuzu_fake,
        embedder=embedder,
        filters={"tags": ["tag3"]},
    )

    assert len(results_user2_tag3) == 1
    assert results_user2_tag3[0].memory.user_id == "user2"
    assert "tag3" in results_user2_tag3[0].memory.tags
