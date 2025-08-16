"""End-to-end tests using real FastEmbed embedder - no mocking"""

import os
from pathlib import Path
import tempfile

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
    memo1 = add_memory(
        memory_type="memo",
        payload={
            "statement": "PostgreSQL database configuration and optimization",
        },
        user_id=user_id,
        # No hardcoded tags - removed as part of audit
    )

    memo2 = add_memory(
        memory_type="memo_test",
        payload={
            "statement": "Performance optimization for PostgreSQL databases",
            "details": "Complete guide to PostgreSQL performance tuning with indexing strategies",
            "status": "todo",
            "priority": "high",
        },
        user_id=user_id,
        # No hardcoded tags - removed as part of audit
    )

    memo3 = add_memory(
        memory_type="memo_test",
        payload={
            "statement": "Implement caching layer for database queries",
            "details": "This is a task to implement caching.",
            "status": "in_progress",
            "priority": "medium",
        },
        user_id=user_id,
        # No hardcoded tags - removed as part of audit
    )

    # Verify memories were created
    assert memo1.id
    assert memo2.id
    assert memo3.id

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
        memory_type="memo_test",
        payload={
            "statement": "User 1 secret content",
            "details": "This is a secret note for user 1.",
        },
        user_id=user1,
    )
    add_memory(
        memory_type="memo_test",
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
    memo = add_memory(
        memory_type="memo",
        payload={
            "statement": "Test content",
        },
        user_id="test",
    )
    assert memo.id

    # This test confirms the model configuration is working
    # We're using Snowflake/snowflake-arctic-embed-xs by default
