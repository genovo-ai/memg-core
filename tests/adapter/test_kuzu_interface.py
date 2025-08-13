"""Tests for KuzuInterface using FakeKuzu."""

import os
import pytest

pytestmark = pytest.mark.adapter
from unittest.mock import patch, MagicMock

from memg_core.core.exceptions import DatabaseError
from memg_core.core.interfaces.kuzu import KuzuInterface


def test_add_node_and_query_roundtrip(kuzu_fake):
    """Test adding a node and querying it back."""
    # Add a node
    node_properties = {
        "id": "test-node-1",
        "user_id": "test-user",
        "content": "Test content",
        "memory_type": "note",
        "title": "Test Title",
        "summary": "",
        "source": "user",
        "tags": "tag1,tag2",
        "confidence": 0.8,
        "is_valid": True,
        "created_at": "2023-01-01T00:00:00+00:00",
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    }

    kuzu_fake.add_node("Memory", node_properties)

    # Query for the node
    query = """
    MATCH (m:Memory)
    WHERE m.id = $id
    RETURN m.id, m.user_id, m.content, m.title, m.memory_type
    """
    params = {"id": "test-node-1"}

    results = kuzu_fake.query(query, params)

    assert len(results) == 1
    assert results[0]["m.id"] == "test-node-1"
    assert results[0]["m.user_id"] == "test-user"
    assert results[0]["m.content"] == "Test content"
    assert results[0]["m.title"] == "Test Title"
    assert results[0]["m.memory_type"] == "note"


def test_add_relationship_and_neighbors_roundtrip(kuzu_fake):
    """Test adding a relationship and querying neighbors."""
    # Add two nodes
    node1_properties = {
        "id": "node-1",
        "user_id": "test-user",
        "content": "Node 1 content",
        "memory_type": "note",
        "title": "Node 1",
        "summary": "",
        "source": "user",
        "tags": "",
        "confidence": 0.8,
        "is_valid": True,
        "created_at": "2023-01-01T00:00:00+00:00",
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    }

    node2_properties = {
        "id": "node-2",
        "user_id": "test-user",
        "content": "Node 2 content",
        "memory_type": "note",
        "title": "Node 2",
        "summary": "",
        "source": "user",
        "tags": "",
        "confidence": 0.8,
        "is_valid": True,
        "created_at": "2023-01-01T00:00:00+00:00",
        "expires_at": "",
        "supersedes": "",
        "superseded_by": "",
    }

    kuzu_fake.add_node("Memory", node1_properties)
    kuzu_fake.add_node("Memory", node2_properties)

    # Add a relationship
    relationship_props = {
        "user_id": "test-user",
        "confidence": 0.9,
        "created_at": "2023-01-01T00:00:00+00:00",
        "is_valid": True,
    }

    kuzu_fake.add_relationship(
        from_table="Memory",
        to_table="Memory",
        rel_type="REFERENCES",
        from_id="node-1",
        to_id="node-2",
        props=relationship_props
    )

    # Query neighbors
    neighbors = kuzu_fake.neighbors(
        node_label="Memory",
        node_id="node-1",
        rel_types=["REFERENCES"],
        direction="out",
        limit=10,
        neighbor_label="Memory"
    )

    assert len(neighbors) == 1
    assert neighbors[0]["id"] == "node-2"
    assert neighbors[0]["content"] == "Node 2 content"
    assert neighbors[0]["rel_type"] == "REFERENCES"


def test_query_empty_returns_list(kuzu_fake):
    """Test that query returns an empty list for no results."""
    # Query for non-existent node
    query = """
    MATCH (m:Memory)
    WHERE m.id = $id
    RETURN m.id, m.user_id, m.content
    """
    params = {"id": "non-existent"}

    results = kuzu_fake.query(query, params)

    assert isinstance(results, list)
    assert len(results) == 0


def test_init_raises_databaseerror_when_db_path_missing():
    """Test that init raises DatabaseError when db_path is missing."""
    # Patch os.environ to remove KUZU_DB_PATH
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(DatabaseError) as exc_info:
            KuzuInterface()

        assert "KUZU_DB_PATH environment variable must be set" in str(exc_info.value)
        assert exc_info.value.operation == "__init__"


def test_add_node_handles_errors():
    """Test that add_node handles errors correctly."""
    # Create a KuzuInterface with a mocked connection
    with patch("kuzu.Database"), patch("kuzu.Connection") as mock_conn:
        # Configure the mock to raise Exception
        mock_conn.return_value.execute.side_effect = Exception("Database error")

        kuzu = KuzuInterface(db_path="/tmp/kuzu")

        # Attempt to add a node
        with pytest.raises(DatabaseError) as exc_info:
            kuzu.add_node("Memory", {"id": "test-id"})

        assert "Database error" in str(exc_info.value)
        assert exc_info.value.operation == "add_node"


def test_add_relationship_validates_nodes(kuzu_fake):
    """Test that add_relationship validates nodes exist."""
    # Add one node but not the other
    node_properties = {
        "id": "node-1",
        "user_id": "test-user",
        "content": "Node 1 content",
    }

    kuzu_fake.add_node("Memory", node_properties)

    # Try to add a relationship to a non-existent node
    with pytest.raises(ValueError) as exc_info:
        kuzu_fake.add_relationship(
            from_table="Memory",
            to_table="Memory",
            rel_type="REFERENCES",
            from_id="node-1",
            to_id="non-existent",
        )

    assert "not found" in str(exc_info.value)
