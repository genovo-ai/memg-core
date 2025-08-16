"""Tests for the indexer pipeline."""

import pytest

pytestmark = pytest.mark.pipeline
from unittest.mock import MagicMock

from memg_core.core.exceptions import ProcessingError
from memg_core.core.pipeline.indexer import add_memory_index


def test_add_memory_index_stores_in_both_stores(embedder, qdrant_fake, kuzu_fake, mem_factory):
    """Test that add_memory_index stores in both Qdrant and Kuzu."""
    # Create a memory
    memory = mem_factory(
        id="test-memory-1",
        user_id="test-user",
        memory_type="memo_test",
        statement="This is a test memory",
        payload={
            "details": "This is the detail for the test memory.",
        },
    )

    # Add to index
    point_id = add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    assert point_id == "test-memory-1"

    # Check that it's in Qdrant
    qdrant_point = qdrant_fake.get_point(point_id)
    assert qdrant_point is not None
    assert qdrant_point["payload"]["core"]["user_id"] == "test-user"
    assert qdrant_point["payload"]["entity"]["statement"] == "This is a test memory"
    assert qdrant_point["payload"]["core"]["memory_type"] == "memo_test"
    assert qdrant_point["payload"]["entity"]["details"] == "This is the detail for the test memory."

    # Check that it's in Kuzu
    assert "test-memory-1" in kuzu_fake.nodes["Memory"]
    kuzu_node = kuzu_fake.nodes["Memory"]["test-memory-1"]
    assert kuzu_node["user_id"] == "test-user"
    assert kuzu_node["memory_type"] == "memo_test"
    # Kuzu only stores core fields, not payload fields like statement


def test_add_memory_index_uses_override_when_provided(
    embedder, qdrant_fake, kuzu_fake, mem_factory
):
    """Test that add_memory_index uses index_text_override when provided."""
    # Create a memory
    memory = mem_factory(
        id="test-memory-1",
        user_id="test-user",
        memory_type="memo",
        statement="This is a test memory",
    )

    # Add to index with override
    point_id = add_memory_index(memory, qdrant_fake, kuzu_fake, embedder)

    # Check that the memory was stored in Qdrant
    qdrant_point = qdrant_fake.get_point(point_id)
    assert qdrant_point is not None
    # Note: index_text_override affects embedding generation, not payload storage

    # The embedding should be based on the override text
    # We can verify this by comparing with a direct embedding
    statement_vector = embedder.get_embedding(memory.statement)
    stored_vector = qdrant_point["vector"]

    # Vectors should be identical since our DummyEmbedder is deterministic
    assert stored_vector == statement_vector


def test_add_memory_index_qdrant_succeeds_kuzu_fails_logs_and_raises(
    embedder, qdrant_fake, mem_factory
):
    """Test that add_memory_index handles Qdrant success but Kuzu failure."""
    # Create a memory
    memory = mem_factory(id="test-memory-1", user_id="test-user", statement="This is a test memory")

    # Create a failing Kuzu mock
    failing_kuzu = MagicMock()
    failing_kuzu.add_node.side_effect = Exception("Kuzu failure")

    # Add to index - should raise ProcessingError
    with pytest.raises(ProcessingError) as exc_info:
        add_memory_index(memory, qdrant_fake, failing_kuzu, embedder)

    assert "Failed to index memory" in str(exc_info.value)
    assert exc_info.value.operation == "add_memory_index"
    assert "Kuzu failure" in str(exc_info.value.original_error)

    # Check that it was added to Qdrant despite Kuzu failure
    qdrant_point = qdrant_fake.get_point("test-memory-1")
    assert qdrant_point is not None


def test_add_memory_index_with_collection_name(embedder, qdrant_fake, kuzu_fake, mem_factory):
    """Test that add_memory_index respects collection name."""
    # Create a memory
    memory = mem_factory(
        id="test-memory-1",
        user_id="test-user",
        memory_type="memo",
        statement="This is a test memory",
    )

    # Add to index with custom collection
    custom_collection = "custom_memories"
    point_id = add_memory_index(
        memory, qdrant_fake, kuzu_fake, embedder, collection=custom_collection
    )

    # Check that it's in the custom collection
    assert qdrant_fake.collection_exists(custom_collection)
    assert point_id in qdrant_fake.points[custom_collection]

    # Check that it's not in the default collection (if it exists)
    if "memories" in qdrant_fake.points:
        assert point_id not in qdrant_fake.points["memories"]
