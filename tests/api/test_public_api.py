"""Tests for the public API contract."""

import os
import pytest
from pathlib import Path

pytestmark = pytest.mark.api
from datetime import UTC, datetime, timedelta
from unittest.mock import patch, MagicMock

from memg_core.api.public import add_memory, search
from memg_core.core.exceptions import ValidationError
from memg_core.core.models import Memory, SearchResult


@pytest.fixture()
def tmp_yaml(tmp_path: Path):
    y = tmp_path / "entities.yaml"
    y.write_text(
        """
version: v1
entities:
  - name: memo
    anchor: statement
    fields:
      id:          { type: string, required: true, system: true }
      user_id:     { type: string, required: true, system: true }
      statement:   { type: string, required: true, max_length: 8000 }
      tags:        { type: tags }
  - name: note
    parent: memo
    anchor: statement
    fields:
      details:     { type: string, required: true }
  - name: document
    parent: memo
    anchor: statement
    fields:
      details:     { type: string, required: true }
  - name: task
    parent: memo
    anchor: statement
    fields:
      details:     { type: string }
      due_date:    { type: datetime }
""",
        encoding="utf-8",
    )
    os.environ["MEMG_YAML_SCHEMA"] = str(y)
    return y


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
            type="note",
            statement="Test content",
            payload={"details": "Test details"},
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


def test_add_memory_note_returns_memory_and_persists(mock_index_memory, tmp_yaml):
    """Test that add_memory for note type returns a Memory and persists it."""
    # Call add_memory with note type
    memory = add_memory(
        memory_type="note",
        payload={
            "statement": "This is a test note",
            "details": "This is the detail for the test note.",
        },
        user_id="test-user",
        tags=["test", "note"]
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a test note"
    assert memory.memory_type == "note"
    assert memory.payload.get("details") == "This is the detail for the test note."
    assert memory.tags == ["test", "note"]

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()

    # Check the memory passed to _index_memory_with_yaml
    indexed_memory = mock_index_memory.call_args[0][0]
    assert indexed_memory.user_id == "test-user"
    assert indexed_memory.statement == "This is a test note"
    assert indexed_memory.memory_type == "note"


def test_add_memory_document_summary_used_in_index_text(mock_index_memory, tmp_yaml):
    """Test that add_memory for document type uses summary in index text."""
    # Call add_memory with document type
    memory = add_memory(
        memory_type="document",
        payload={
            "statement": "This is a document summary",
            "details": "This is a long document content",
        },
        user_id="test-user",
        tags=["test", "document"]
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a document summary"
    assert memory.memory_type == "document"
    assert memory.payload.get("details") == "This is a long document content"
    assert memory.tags == ["test", "document"]

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()


def test_add_memory_task_due_date_serialized(mock_index_memory, tmp_yaml):
    """Test that add_memory for task type serializes dates correctly."""
    # Create a due date
    due_date = datetime.now(UTC) + timedelta(days=1)

    # Call add_memory with task type
    memory = add_memory(
        memory_type="task",
        payload={
            "statement": "This is a test task",
            "due_date": due_date.isoformat(),
        },
        user_id="test-user",
        tags=["test", "task"]
    )

    # Check that the memory was created correctly
    assert memory.id == "test-memory-id"
    assert memory.user_id == "test-user"
    assert memory.statement == "This is a test task"
    assert memory.memory_type == "task"
    assert memory.payload.get("due_date") == due_date.isoformat()
    assert memory.tags == ["test", "task"]

    # Check that _index_memory_with_yaml was called
    mock_index_memory.assert_called_once()


def test_search_requires_user_id_raises_valueerror(mock_graph_rag_search):
    """Test that search requires user_id and raises ValueError if missing."""
    # Call search without user_id
    with pytest.raises(ValidationError) as exc_info:
        search(query="test query", user_id="")

    assert "User ID is required" in str(exc_info.value)

    # Call search with None user_id
    with pytest.raises(ValidationError) as exc_info:
        search(query="test query", user_id=None)

    assert "User ID is required" in str(exc_info.value)


def test_search_plugin_absent_does_not_crash():
    """Test that search works when YAML plugin is absent."""
    # Mock dependencies
    with patch("memg_core.api.public.get_config") as mock_config, \
         patch("memg_core.api.public.QdrantInterface") as mock_qdrant, \
         patch("memg_core.api.public.KuzuInterface") as mock_kuzu, \
         patch("memg_core.api.public.Embedder") as mock_embedder, \
         patch("memg_core.api.public.graph_rag_search") as mock_search:

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
            type="note",
            statement="Test content",
            payload={"details": "Test details"},
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
    with patch("memg_core.api.public.get_config") as mock_config, \
         patch("memg_core.api.public.QdrantInterface") as mock_qdrant, \
         patch("memg_core.api.public.KuzuInterface") as mock_kuzu, \
         patch("memg_core.api.public.Embedder") as mock_embedder, \
         patch("memg_core.api.public.graph_rag_search") as mock_search:

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
            type="note",
            statement="Test content",
            payload={"details": "Test details"},
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
