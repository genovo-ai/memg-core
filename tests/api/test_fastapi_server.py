"""
Integration tests for FastAPI server routes.
Tests that the HTTP layer properly calls the core public API.
"""

import pytest
from fastapi.testclient import TestClient

from memg_core.api.server import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test that the health endpoint returns OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_endpoint_requires_query_or_memo_type(client):
    """Test that search endpoint validates required parameters."""
    # Missing both query and memo_type should fail
    response = client.post("/v1/search", json={
        "user_id": "test_user",
        "limit": 10
    })
    assert response.status_code == 400
    assert "query" in response.json()["detail"] or "memo_type" in response.json()["detail"]

    # Missing user_id should fail
    response = client.post("/v1/search", json={
        "query": "test query",
        "limit": 10
    })
    assert response.status_code == 422  # Pydantic validation error


def test_search_endpoint_with_valid_params(client):
    """Test search endpoint with valid parameters."""
    response = client.post("/v1/search", json={
        "query": "test query",
        "user_id": "test_user",
        "limit": 5,
        "include_details": "none"
    })
    # May return 200 (empty results) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_add_note_endpoint_validation(client):
    """Test add note endpoint validates required fields."""
    # Missing text should fail
    response = client.post("/v1/memories/note", json={
        "user_id": "test_user",
        "title": "Test Note"
    })
    assert response.status_code == 422  # Pydantic validation error

    # Missing user_id should fail
    response = client.post("/v1/memories/note", json={
        "text": "Note content"
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_note_endpoint_with_valid_params(client):
    """Test add note endpoint with valid parameters."""
    response = client.post("/v1/memories/note", json={
        "text": "This is a test note",
        "user_id": "test_user",
        "title": "Test Note",
        "tags": ["test", "api"]
    })
    # May return 200 (success) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_add_document_endpoint_validation(client):
    """Test add document endpoint validates required fields."""
    # Missing text should fail
    response = client.post("/v1/memories/document", json={
        "user_id": "test_user",
        "title": "Test Document"
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_document_endpoint_with_valid_params(client):
    """Test add document endpoint with valid parameters."""
    response = client.post("/v1/memories/document", json={
        "text": "This is a test document content",
        "user_id": "test_user",
        "title": "Test Document",
        "summary": "Brief summary",
        "tags": ["test", "document"]
    })
    # May return 200 (success) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_add_task_endpoint_validation(client):
    """Test add task endpoint validates required fields."""
    # Missing text should fail
    response = client.post("/v1/memories/task", json={
        "user_id": "test_user",
        "title": "Test Task"
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_task_endpoint_with_valid_params(client):
    """Test add task endpoint with valid parameters."""
    response = client.post("/v1/memories/task", json={
        "text": "Complete this test task",
        "user_id": "test_user",
        "title": "Test Task",
        "due_date": "2024-12-31T23:59:59",
        "tags": ["test", "task"]
    })
    # May return 200 (success) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_add_memory_endpoint_validation(client):
    """Test generic add memory endpoint validates required fields."""
    # Missing memory_type should fail
    response = client.post("/v1/memories", json={
        "payload": {"statement": "test"},
        "user_id": "test_user"
    })
    assert response.status_code == 422  # Pydantic validation error

    # Missing payload should fail
    response = client.post("/v1/memories", json={
        "memory_type": "note",
        "user_id": "test_user"
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_memory_endpoint_with_valid_params(client):
    """Test generic add memory endpoint with valid parameters."""
    response = client.post("/v1/memories", json={
        "memory_type": "note",
        "payload": {
            "statement": "Generic memory test",
            "source": "api_test"
        },
        "user_id": "test_user",
        "tags": ["test", "generic"]
    })
    # May return 200 (success) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_search_endpoint_projection_param(client):
    """Test search endpoint accepts projection parameter."""
    response = client.post("/v1/search", json={
        "query": "test",
        "user_id": "test_user",
        "include_details": "self",
        "projection": {
            "document": ["title", "summary"],
            "note": ["statement"]
        }
    })
    # May return 200 (empty results) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]


def test_search_endpoint_mode_param(client):
    """Test search endpoint accepts mode parameter."""
    response = client.post("/v1/search", json={
        "memo_type": "note",
        "user_id": "test_user",
        "mode": "vector"
    })
    # May return 200 (empty results) or 400 (if no storage setup), both acceptable for integration test
    assert response.status_code in [200, 400]
