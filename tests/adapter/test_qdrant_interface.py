"""Tests for QdrantInterface using FakeQdrant."""

import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.adapter

from memg_core.core.exceptions import DatabaseError
from memg_core.core.interfaces.qdrant import QdrantInterface


def test_create_and_search_points_basic_match(qdrant_fake):
    """Test creating and searching points with basic matching."""
    # Add a point
    vector = [0.1, 0.2, 0.3]
    payload = {"user_id": "test-user", "content": "Test content"}
    success, point_id = qdrant_fake.add_point(vector=vector, payload=payload)

    assert success is True
    assert point_id is not None

    # Search for the point
    results = qdrant_fake.search_points(vector=vector, limit=5)

    assert len(results) == 1
    assert results[0]["id"] == point_id
    assert results[0]["payload"] == payload
    assert results[0]["score"] > 0.99  # Should be very close to 1.0 for exact match


def test_filter_points_by_user_and_tags(qdrant_fake):
    """Test filtering points by user_id and tags."""
    # Add points for different users
    vector1 = [0.1, 0.2, 0.3]
    vector2 = [0.2, 0.3, 0.4]
    vector3 = [0.3, 0.4, 0.5]

    qdrant_fake.add_point(
        vector=vector1,
        payload={"user_id": "user1", "content": "User 1 content", "tags": ["tag1", "tag2"]}
    )
    qdrant_fake.add_point(
        vector=vector2,
        payload={"user_id": "user1", "content": "User 1 content 2", "tags": ["tag2", "tag3"]}
    )
    qdrant_fake.add_point(
        vector=vector3,
        payload={"user_id": "user2", "content": "User 2 content", "tags": ["tag1", "tag3"]}
    )

    # Search with user_id filter
    results_user1 = qdrant_fake.search_points(
        vector=vector1,
        limit=10,
        user_id="user1"
    )

    assert len(results_user1) == 2
    assert all(r["payload"]["user_id"] == "user1" for r in results_user1)

    # Search with user_id and tags filter
    results_user1_tag2 = qdrant_fake.search_points(
        vector=vector1,
        limit=10,
        user_id="user1",
        filters={"tags": ["tag2"]}
    )

    assert len(results_user1_tag2) == 2
    assert all(r["payload"]["user_id"] == "user1" for r in results_user1_tag2)
    assert all("tag2" in r["payload"]["tags"] for r in results_user1_tag2)

    # Search with specific tag
    results_tag1 = qdrant_fake.search_points(
        vector=vector1,
        limit=10,
        filters={"tags": ["tag1"]}
    )

    assert len(results_tag1) == 2
    assert all("tag1" in r["payload"]["tags"] for r in results_tag1)


def test_get_point_returns_payload_only(qdrant_fake):
    """Test that get_point returns the payload only."""
    # Add a point
    vector = [0.1, 0.2, 0.3]
    payload = {"user_id": "test-user", "content": "Test content"}
    success, point_id = qdrant_fake.add_point(vector=vector, payload=payload)

    # Get the point
    result = qdrant_fake.get_point(point_id)

    assert result is not None
    assert result["id"] == point_id
    assert result["payload"] == payload
    assert result["vector"] == vector


def test_delete_point_removes_document(qdrant_fake):
    """Test that delete_points removes the document."""
    # Add a point
    vector = [0.1, 0.2, 0.3]
    payload = {"user_id": "test-user", "content": "Test content"}
    success, point_id = qdrant_fake.add_point(vector=vector, payload=payload)

    # Verify the point exists
    assert qdrant_fake.get_point(point_id) is not None

    # Delete the point
    success = qdrant_fake.delete_points([point_id])

    assert success is True
    assert qdrant_fake.get_point(point_id) is None


def test_search_raises_networkerror_on_connection_failure():
    """Test that search_points raises DatabaseError on connection failure."""
    # Create a QdrantInterface with a mocked client
    with patch("memg_core.core.interfaces.qdrant.QdrantClient") as mock_client:
        # Configure the mock to raise ConnectionError on query_points
        mock_instance = MagicMock()
        mock_instance.query_points.side_effect = ConnectionError("Connection failed")
        mock_client.return_value = mock_instance

        qdrant = QdrantInterface(storage_path="/tmp/qdrant_test1")

        # Attempt to search
        with pytest.raises(DatabaseError) as exc_info:
            qdrant.search_points(vector=[0.1, 0.2, 0.3])

        assert "Connection failed" in str(exc_info.value)
        assert exc_info.value.operation == "search_points"


def test_collection_exists_handles_errors():
    """Test that collection_exists handles errors correctly."""
    # Create a QdrantInterface with a mocked client
    with patch("memg_core.core.interfaces.qdrant.QdrantClient") as mock_client:
        # Configure the mock to raise Exception on get_collections
        mock_instance = MagicMock()
        mock_instance.get_collections.side_effect = Exception("Unknown error")
        mock_client.return_value = mock_instance

        qdrant = QdrantInterface(storage_path="/tmp/qdrant_test2")

        # Attempt to check if collection exists
        with pytest.raises(DatabaseError) as exc_info:
            qdrant.collection_exists()

        assert "Unknown error" in str(exc_info.value)
        assert exc_info.value.operation == "collection_exists"
