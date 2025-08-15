"""Integration tests for the memory system.

These tests require real Qdrant and Kuzu instances to be running.
They are marked with the 'integration' marker and can be skipped with:
pytest -m "not integration"
"""

from datetime import UTC, datetime
import os
from uuid import uuid4

import pytest

from memg_core.core.interfaces.embedder import Embedder
from memg_core.core.interfaces.kuzu import KuzuInterface
from memg_core.core.interfaces.qdrant import QdrantInterface
from memg_core.core.models import Memory


@pytest.mark.integration
def test_index_and_search_with_real_qdrant():
    """Test indexing and searching with a real Qdrant instance."""
    # No API key needed for FastEmbed - it's offline!

    # Skip if no Qdrant path
    if not os.environ.get("QDRANT_STORAGE_PATH"):
        pytest.skip("QDRANT_STORAGE_PATH environment variable not set")

    # Create real interfaces
    qdrant = QdrantInterface(collection_name="test_memories")
    embedder = Embedder()

    # Create a test memory
    memory = Memory(
        id="12345678-1234-5678-1234-567812345678",  # Valid UUID format
        user_id="test-user",
        memory_type="note",
        payload={
            "content": "This is an integration test memory",  # YAML schema: note uses content
        },
        created_at=datetime.now(UTC),
    )

    try:
        # Add to Qdrant
        vector = embedder.get_embedding(memory.content)
        success, point_id = qdrant.add_point(
            vector=vector,
            payload=memory.to_qdrant_payload(),
            point_id=memory.id,
        )

        assert success is True
        assert point_id == "12345678-1234-5678-1234-567812345678"

        # Search
        results = qdrant.search_points(
            vector=vector,
            limit=5,
            # real adapter filters by payload path; pass filters instead of user_id param
            filters={"core.user_id": "test-user"},
        )

        assert len(results) > 0
        assert results[0]["id"] == "12345678-1234-5678-1234-567812345678"
        # Check the payload structure - content is in entity.content for notes
        payload = results[0]["payload"]
        assert payload["entity"]["content"] == "This is an integration test memory"

    finally:
        # Clean up
        qdrant.delete_points(["12345678-1234-5678-1234-567812345678"])


@pytest.mark.integration
def test_graph_neighbors_with_real_kuzu():
    """Test graph neighbors with a real Kuzu instance."""
    # Skip if no Kuzu path
    if not os.environ.get("KUZU_DB_PATH"):
        pytest.skip("KUZU_DB_PATH environment variable not set")

    # Create real Kuzu interface
    kuzu = KuzuInterface()

    # Create test nodes
    node1 = {
        "id": "test-node-1",
        "user_id": "test-user",
        "content": "Test node 1",
        "memory_type": "note",
        "summary": "",
        "source": "user",
        "confidence": 0.8,
        "is_valid": 1.0,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    }

    node2 = {
        "id": "test-node-2",
        "user_id": "test-user",
        "content": "Test node 2",
        "memory_type": "note",
        "summary": "",
        "source": "user",
        "confidence": 0.8,
        "is_valid": 1.0,
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    }

    try:
        # use unique IDs to avoid PK collisions if DB persists
        node1_id = f"test-node-{uuid4()}"
        node2_id = f"test-node-{uuid4()}"
        node1["id"] = node1_id
        node2["id"] = node2_id
        kuzu.add_node("Memory", node1)
        kuzu.add_node("Memory", node2)

        # Add relationship using YAML-defined predicate
        kuzu.add_relationship(
            from_table="Memory",
            to_table="Memory",
            rel_type="RELATED_TO",  # Valid YAML predicate from memo_related relation
            from_id=node1_id,
            to_id=node2_id,
        )

        # Query neighbors
        neighbors = kuzu.neighbors(
            node_label="Memory",
            node_id=node1_id,
            direction="out",
            limit=10,
            neighbor_label="Memory",
        )

        assert len(neighbors) == 1
        assert neighbors[0]["id"] == node2_id
        assert neighbors[0]["rel_type"] == "RELATED_TO"

    finally:
        # Clean up - would require a delete operation in production
        # For testing, we'll leave it since we can't easily delete nodes in Kuzu
        pass
