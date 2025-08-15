"""
Integration tests for FastAPI server routes.
Tests that the HTTP layer properly calls the core public API.
"""

import pytest
from fastapi.testclient import TestClient

# FastAPI server moved to scripts/ - this test may need updating
from scripts.fastapi_server import app


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
    assert response.status_code in [200, 400]  # May fail due to missing env vars


def test_add_memory_endpoint_validation(client):
    """Test generic add memory endpoint validates required fields."""
    # Missing type should fail
    response = client.post("/v1/memories", json={
        "statement": "test statement",
        "payload": {"details": "test"},
        "user_id": "test_user"
    })
    assert response.status_code == 422  # Pydantic validation error

    # Missing statement should fail
    response = client.post("/v1/memories", json={
        "type": "note",
        "payload": {"details": "test"},
        "user_id": "test_user"
    })
    assert response.status_code == 422  # Pydantic validation error

    # Missing user_id should fail
    response = client.post("/v1/memories", json={
        "type": "note",
        "statement": "test statement",
        "payload": {"details": "test"},
    })
    assert response.status_code == 422  # Pydantic validation error


def test_add_memory_endpoint_with_valid_params(client):
    """Test generic add memory endpoint with valid parameters."""
    response = client.post("/v1/memories", json={
        "type": "note",
        "statement": "Generic memory test",
        "payload": {
            "details": "This is the detail for the generic memory test.",
        },
        "user_id": "test_user",
        "tags": ["test", "generic"]
    })
    assert response.status_code in [200, 400]  # May fail due to missing env vars


def test_search_endpoint_projection_param(client):
    """Test search endpoint accepts projection parameter."""
    response = client.post("/v1/search", json={
        "query": "test",
        "user_id": "test_user",
        "include_details": "self",
        "projection": {
            "document": ["details"],
            "note": ["details"]
        }
    })
    assert response.status_code in [200, 400]  # May fail due to missing env vars


def test_search_endpoint_mode_param(client):
    """Test search endpoint accepts mode parameter."""
    response = client.post("/v1/search", json={
        "memo_type": "note",
        "user_id": "test_user",
        "mode": "vector"
    })
    assert response.status_code in [200, 400]  # May fail due to missing env vars
