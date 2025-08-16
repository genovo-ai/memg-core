"""Tests for the public API contract."""

import pytest

pytestmark = pytest.mark.api
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from memg_core.api.public import add_memory, search
from memg_core.core.exceptions import ValidationError
from memg_core.core.models import Memory, SearchResult


@pytest.fixture
def mock_index_memory():
    """Fixture to mock the _index_memory_with_yaml function."""
    with patch("memg_core.api.public._index_memory_with_yaml") as mock:
        mock.return_value = "test-memory-id"
        yield mock


@pytest.fixture
def mock_graph_rag_search():
    """Fixture to mock the graph_rag_search function."""
    with patch("memg_core.api.public.graph_rag_search") as mock:
        # Create a sample search result
        memory = Memory(
            id="test-memory-id",
            user_id="test-user",
            memory_type="memo_test",
            payload={"statement": "Test content", "details": "Test details"},
        )
        result = SearchResult(
            memory=memory,
            score=0.9,
            distance=None,
            source="test",
            metadata={},
        )
        mock.return_value = [result]
        yield mock


def test_add_memory_memo_test_returns_memory_and_persists(mock_index_memory):
    """Test that add_memory for memo_test type returns a Memory and persists it."""
    # Call add_memory with memo_test type
    memory = add_memory(
        memory_type="memo_test",
        payload={
            "statement": "This is a test memo_test",
            "details": "This is the detail for the test memo_test.",
        },
        user_id="test-user",
        # No hardcoded tags - removed as part of audit
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a test memo_test"
    assert memory.memory_type == "memo_test"
    assert memory.payload.get("details") == "This is the detail for the test memo_test."
    # No hardcoded tags - removed as part of audit

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()

    # Check the memory passed to _index_memory_with_yaml
    indexed_memory = mock_index_memory.call_args[0][0]
    assert indexed_memory.user_id == "test-user"
    assert indexed_memory.statement == "This is a test memo_test"
    assert indexed_memory.memory_type == "memo_test"


def test_add_memory_memo_summary_used_in_index_text(mock_index_memory):
    """Test that add_memory for memo type uses summary in index text."""
    # Call add_memory with memo type
    memory = add_memory(
        memory_type="memo",
        payload={
            "statement": "This is a memo summary",
        },
        user_id="test-user",
        # No hardcoded tags - removed as part of audit
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a memo summary"
    assert memory.memory_type == "memo"
    # No hardcoded tags - removed as part of audit

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()


def test_add_memory_memo_test_due_date_serialized(mock_index_memory):
    """Test that add_memory for memo_test type serializes dates correctly."""
    # Create a due date
    due_date = datetime.now(UTC) + timedelta(days=1)

    # Call add_memory with memo_test type
    memory = add_memory(
        memory_type="memo_test",
        payload={
            "statement": "This is a test memo_test",
            "due_date": due_date.isoformat(),
        },
        user_id="test-user",
        # No hardcoded tags - removed as part of audit
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a test memo_test"
    assert memory.memory_type == "memo_test"
    assert memory.payload.get("due_date") == due_date.isoformat()
    # No hardcoded tags - removed as part of audit

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()


def test_search_requires_user_id_raises_valueerror(mock_graph_rag_search):
    """Test that search requires user_id and raises ValueError if missing."""
    # Call search without user_id
    with pytest.raises(ValidationError) as exc_info:
        search(query="test query", user_id="")

    assert "User ID is required" in str(exc_info.value)

    # Call search with None user_id (type: ignore for testing error case)
    with pytest.raises(ValidationError) as exc_info:
        search(query="test query", user_id=None)  # type: ignore

    assert "User ID is required" in str(exc_info.value)


def test_search_plugin_absent_does_not_crash():
    """Test that search works when YAML plugin is absent."""
    # Mock dependencies
    with (
        patch("memg_core.api.public.get_config") as mock_config,
        patch("memg_core.api.public.QdrantInterface") as mock_qdrant,
        patch("memg_core.api.public.KuzuInterface") as mock_kuzu,
        patch("memg_core.api.public.Embedder") as mock_embedder,
        patch("memg_core.api.public.graph_rag_search") as mock_search,
    ):
        # Configure mocks
        mock_config.return_value = MagicMock()
        mock_config.return_value.memg.qdrant_collection_name = "memories"
        mock_config.return_value.memg.kuzu_database_path = "/tmp/kuzu"

        mock_qdrant.return_value = MagicMock()
        mock_kuzu.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()

        # Mock search result
        memory = Memory(
            id="test-memory-id",
            user_id="test-user",
            memory_type="memo_test",
            payload={"statement": "Test content", "details": "Test details"},
        )
        result = SearchResult(
            memory=memory,
            score=0.9,
            distance=None,
            source="test",
            metadata={},
        )
        mock_search.return_value = [result]

        # Call search - should not crash
        results = search(query="test query", user_id="test-user")

        # Check that search was called
        mock_search.assert_called_once()

        # Check results
        assert len(results) == 1
        assert results[0].memory.id == "test-memory-id"


def test_api_reads_neighbor_cap_env_and_passes_to_pipeline(monkeypatch):
    """Test that API reads neighbor_cap from env and passes to pipeline."""
    # Set environment variable
    monkeypatch.setenv("MEMG_GRAPH_NEIGHBORS_LIMIT", "10")

    # Mock dependencies
    with (
        patch("memg_core.api.public.get_config") as mock_config,
        patch("memg_core.api.public.QdrantInterface") as mock_qdrant,
        patch("memg_core.api.public.KuzuInterface") as mock_kuzu,
        patch("memg_core.api.public.Embedder") as mock_embedder,
        patch("memg_core.api.public.graph_rag_search") as mock_search,
    ):
        # Configure mocks
        mock_config.return_value = MagicMock()
        mock_config.return_value.memg.qdrant_collection_name = "memories"
        mock_config.return_value.memg.kuzu_database_path = "/tmp/kuzu"

        mock_qdrant.return_value = MagicMock()
        mock_kuzu.return_value = MagicMock()
        mock_embedder.return_value = MagicMock()

        # Mock search result
        memory = Memory(
            id="test-memory-id",
            user_id="test-user",
            memory_type="memo_test",
            payload={"statement": "Test content", "details": "Test details"},
        )
        result = SearchResult(
            memory=memory,
            score=0.9,
            distance=None,
            source="test",
            metadata={},
        )
        mock_search.return_value = [result]

        # Call search
        search(query="test query", user_id="test-user")

        # Check that graph_rag_search was called with neighbor_cap=10
        mock_search.assert_called_once()
        assert mock_search.call_args[1].get("neighbor_cap") == 10
