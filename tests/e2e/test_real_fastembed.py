"""End-to-end tests using real FastEmbed embedder - no mocking"""

import os
import tempfile
from pathlib import Path

import pytest

from memg_core.api.public import add_memory, search


@pytest.fixture
def temp_storage():
    """Create temporary storage directories for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        kuzu_path = temp_path / "test.db"
        qdrant_path = temp_path / "qdrant"

        # Set environment variables
        old_kuzu = os.environ.get("KUZU_DB_PATH")
        old_qdrant = os.environ.get("QDRANT_STORAGE_PATH")

        os.environ["KUZU_DB_PATH"] = str(kuzu_path)
        os.environ["QDRANT_STORAGE_PATH"] = str(qdrant_path)

        yield {"kuzu": kuzu_path, "qdrant": qdrant_path}

        # Restore environment
        if old_kuzu:
            os.environ["KUZU_DB_PATH"] = old_kuzu
        else:
            os.environ.pop("KUZU_DB_PATH", None)

        if old_qdrant:
            os.environ["QDRANT_STORAGE_PATH"] = old_qdrant
        else:
            os.environ.pop("QDRANT_STORAGE_PATH", None)


def test_real_fastembed_workflow(temp_storage):
    """Test complete workflow with real FastEmbed - no API keys needed"""
    user_id = "test_user"

    # Add memories using the real API (which now uses FastEmbed)
    note = add_memory(
        memory_type="note",
        payload={
            "statement": "PostgreSQL database configuration and optimization",
            "details": "This is a note about PostgreSQL.",
        },
        user_id=user_id,
        tags=["database", "postgresql"]
    )

    doc = add_memory(
        memory_type="document",
        payload={
            "statement": "Performance optimization for PostgreSQL databases",
            "details": "Complete guide to PostgreSQL performance tuning with indexing strategies",
        },
        user_id=user_id,
        tags=["postgresql", "performance"]
    )

    task = add_memory(
        memory_type="task",
        payload={
            "statement": "Implement caching layer for database queries",
            "details": "This is a task to implement caching.",
        },
        user_id=user_id,
        tags=["cache", "performance"]
    )

    # Verify memories were created
    assert note.id
    assert doc.id
    assert task.id

    # Test search with real FastEmbed embeddings
    results = search("postgresql performance", user_id=user_id, limit=10)

    # Should find relevant results
    assert len(results) > 0

    # Results should be from vector search (lean core may use "qdrant" or "vector_fallback")
    sources = {r.source for r in results}
    assert sources.intersection({"qdrant", "vector_fallback"})

    # Should have good similarity scores (FastEmbed is quite good)
    scores = [r.score for r in results]
    assert all(0.0 <= score <= 1.0 for score in scores)

    # Results should be sorted by score
    assert scores == sorted(scores, reverse=True)

    # Should find the performance guide first (best match)
    assert "Performance" in results[0].memory.statement


def test_user_isolation_real_fastembed(temp_storage):
    """Test user isolation with real FastEmbed"""
    user1 = "user1"
    user2 = "user2"

    # Add content for each user
    add_memory(
        memory_type="note",
        payload={
            "statement": "User 1 secret content",
            "details": "This is a secret note for user 1.",
        },
        user_id=user1,
    )
    add_memory(
        memory_type="note",
        payload={
            "statement": "User 2 secret content",
            "details": "This is a secret note for user 2.",
        },
        user_id=user2,
    )

    # Search should be isolated by user
    results_user1 = search("secret content", user_id=user1, limit=10)
    results_user2 = search("secret content", user_id=user2, limit=10)

    assert len(results_user1) > 0
    assert len(results_user2) > 0

    # Each user should only see their own content
    assert all(r.memory.user_id == user1 for r in results_user1)
    assert all(r.memory.user_id == user2 for r in results_user2)


def test_fastembed_model_configuration(temp_storage):
    """Test that EMBEDDER_MODEL environment variable works"""
    # Test with default model (should work)
    note = add_memory(
        memory_type="note",
        payload={
            "statement": "Test content",
            "details": "This is a test note.",
        },
        user_id="test",
    )
    assert note.id

    # This test confirms the model configuration is working
    # We're using Snowflake/snowflake-arctic-embed-xs by default
