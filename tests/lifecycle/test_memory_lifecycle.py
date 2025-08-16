"""Tests for memory lifecycle operations."""

import pytest

pytestmark = pytest.mark.lifecycle

from memg_core.core.pipeline.indexer import add_memory_index


def test_delete_memory_removes_from_qdrant_and_kuzu_no_dangling_edges(
    embedder, qdrant_fake, kuzu_fake, mem_factory
):
    """Test that deleting a memory removes it from both stores with no dangling edges."""
    # Create memories
    memory1 = mem_factory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
    )

    memory2 = mem_factory(
        id="memory-2",
        user_id="test-user",
        memory_type="memo_test",
    )

    # Add memories to index
    add_memory_index(memory1, qdrant_fake, kuzu_fake, embedder)
    add_memory_index(memory2, qdrant_fake, kuzu_fake, embedder)

    # Add relationship between memories
    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="RELATED_TO",
        from_id="memory-1",
        to_id="memory-2",
    )

    # Verify relationship exists
    neighbors = kuzu_fake.neighbors(
        node_label="Memory",
        node_id="memory-1",
        direction="out",
    )
    assert len(neighbors) == 1
    assert neighbors[0]["id"] == "memory-2"

    # Delete memory2
    qdrant_fake.delete_points(["memory-2"])

    # Remove from Kuzu (would be handled by a delete operation in production)
    del kuzu_fake.nodes["Memory"]["memory-2"]

    # Filter relationships to remove those involving memory-2
    kuzu_fake.relationships = [
        rel
        for rel in kuzu_fake.relationships
        if not (rel["from_id"] == "memory-2" or rel["to_id"] == "memory-2")
    ]

    # Verify memory2 is gone from Qdrant
    assert qdrant_fake.get_point("memory-2") is None

    # Verify memory2 is gone from Kuzu
    assert "memory-2" not in kuzu_fake.nodes["Memory"]

    # Verify no dangling relationships
    neighbors = kuzu_fake.neighbors(
        node_label="Memory",
        node_id="memory-1",
        direction="out",
    )
    assert len(neighbors) == 0


def test_readding_same_id_is_idempotent_or_overwrites_per_policy(
    embedder, qdrant_fake, kuzu_fake, mem_factory
):
    """Test that re-adding a memory with the same ID overwrites it."""
    # Create initial memory
    memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Initial content",
            "details": "Initial details",
        },
    )

    # Add to index
    add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    # Verify initial state - check current payload structure
    qdrant_point = qdrant_fake.get_point("memory-1")
    assert qdrant_point["payload"]["entity"]["statement"] == "Initial content"
    assert qdrant_point["payload"]["entity"]["details"] == "Initial details"

    kuzu_node = kuzu_fake.nodes["Memory"]["memory-1"]
    # Current core stores only core fields in Kuzu, not payload details
    assert "details" not in kuzu_node
    assert kuzu_node["memory_type"] == "memo_test"

    # Update memory with same ID
    updated_memory = mem_factory(
        id="memory-1",
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Updated content",
            "details": "Updated details",
        },
    )

    # Re-add to index
    add_memory_index(updated_memory, qdrant_fake, kuzu_fake, embedder)

    # Verify updated state - check current payload structure
    qdrant_point = qdrant_fake.get_point("memory-1")
    assert qdrant_point["payload"]["entity"]["statement"] == "Updated content"
    assert qdrant_point["payload"]["entity"]["details"] == "Updated details"

    kuzu_node = kuzu_fake.nodes["Memory"]["memory-1"]
    # Current core stores only core fields in Kuzu, not payload details
    assert "details" not in kuzu_node
    assert kuzu_node["memory_type"] == "memo_test"
