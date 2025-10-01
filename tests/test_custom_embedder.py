"""Tests for custom embedder functionality.

Validates that consumers can provide their own embedder implementations
and that they are used correctly throughout the memory lifecycle.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from memg_core import MemgClient
from memg_core.utils.db_clients import DatabaseClients

if TYPE_CHECKING:
    from pathlib import Path


# Override the global mock_embedder fixture for these tests
@pytest.fixture(autouse=True)
def mock_embedder():
    """Override global fixture - don't mock the embedder in these tests."""
    # Just yield without any mocking - we want to test real embedder behavior
    yield None


class MockEmbedder:
    """Simple mock embedder for testing."""

    def __init__(self, dimension: int = 384):
        """Initialize with a specific embedding dimension."""
        self.dimension = dimension
        self.call_count = 0
        self.call_history: list[str] = []

    def get_embedding(self, text: str) -> list[float]:
        """Return a deterministic embedding based on text length."""
        self.call_count += 1
        self.call_history.append(text)
        # Create a simple embedding: text length repeated to match dimension
        base = float(len(text))
        return [base] * self.dimension

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for multiple texts."""
        return [self.get_embedding(text) for text in texts]


def test_mock_embedder_implements_protocol():
    """MockEmbedder should have the required methods for the protocol."""
    embedder = MockEmbedder()
    # Protocol is for type checking, not runtime - verify methods exist
    assert hasattr(embedder, "get_embedding")
    assert hasattr(embedder, "get_embeddings")
    assert callable(embedder.get_embedding)
    assert callable(embedder.get_embeddings)


def test_database_clients_accepts_custom_embedder():
    """DatabaseClients should accept and use custom embedder."""
    mock = MockEmbedder()
    clients = DatabaseClients(embedder=mock)

    # Should return the provided embedder
    embedder = clients.get_embedder()
    assert embedder is mock

    # Verify it works
    result = embedder.get_embedding("test")
    assert result == [4.0] * 384  # "test" has 4 chars
    assert mock.call_count == 1


def test_database_clients_uses_default_when_no_embedder_provided():
    """DatabaseClients should create default embedder when none provided."""
    clients = DatabaseClients()

    # First call creates the embedder
    embedder1 = clients.get_embedder()
    assert embedder1 is not None

    # Second call returns the same instance (singleton within client)
    embedder2 = clients.get_embedder()
    assert embedder2 is embedder1


def test_memg_client_with_custom_embedder(tmp_path: Path):
    """MemgClient should accept and use custom embedder through full memory lifecycle."""
    # Setup
    yaml_path = os.environ.get("MEMG_YAML_PATH", "config/core.test.yaml")
    db_path = str(tmp_path / "custom_embedder_test")

    mock = MockEmbedder()
    client = MemgClient(yaml_path=yaml_path, db_path=db_path, embedder=mock)

    # Add a memory - should trigger embedding
    hrid = client.add_memory(
        memory_type="note",
        payload={"statement": "Testing custom embedder", "project": "test"},
        user_id="test_user",
    )

    # Verify embedder was called with the anchor text
    assert mock.call_count == 1
    assert "Testing custom embedder" in mock.call_history[0]

    # Search should also use custom embedder
    results = client.search(query="custom embedder", user_id="test_user", limit=5)

    # Another embedding call for the search query
    assert mock.call_count == 2
    assert "custom embedder" in mock.call_history[1]

    # Should find our memory
    assert len(results.memories) > 0
    found = any(m.hrid == hrid for m in results.memories)
    assert found

    client.close()


def test_memg_client_without_custom_embedder_uses_default(tmp_path: Path):
    """MemgClient without embedder should use default FastEmbed implementation."""
    yaml_path = os.environ.get("MEMG_YAML_PATH", "config/core.test.yaml")
    db_path = str(tmp_path / "default_embedder_test")

    # No custom embedder provided
    client = MemgClient(yaml_path=yaml_path, db_path=db_path)

    # Should still work with default embedder
    hrid = client.add_memory(
        memory_type="note",
        payload={"statement": "Testing default embedder", "project": "test"},
        user_id="test_user",
    )

    assert hrid is not None
    assert hrid.startswith("NOTE_")

    # Search should work
    results = client.search(query="default embedder", user_id="test_user", limit=5)
    assert len(results.memories) > 0

    client.close()


def test_custom_embedder_with_different_dimension():
    """Custom embedders can use different dimensions."""
    # Create embedder with different dimension
    mock = MockEmbedder(dimension=128)
    clients = DatabaseClients(embedder=mock)

    embedder = clients.get_embedder()
    result = embedder.get_embedding("hello")

    assert len(result) == 128
    assert all(x == 5.0 for x in result)  # "hello" has 5 chars


def test_embedder_protocol_duck_typing():
    """Any object with get_embedding/get_embeddings methods should work."""

    class MinimalEmbedder:
        """Minimal embedder without inheriting anything."""

        def get_embedding(self, text: str) -> list[float]:
            return [1.0, 2.0, 3.0]

        def get_embeddings(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 2.0, 3.0] for _ in texts]

    minimal = MinimalEmbedder()
    # Verify it has the protocol methods (duck typing)
    assert hasattr(minimal, "get_embedding") and callable(minimal.get_embedding)
    assert hasattr(minimal, "get_embeddings") and callable(minimal.get_embeddings)

    clients = DatabaseClients(embedder=minimal)
    embedder = clients.get_embedder()
    assert embedder.get_embedding("test") == [1.0, 2.0, 3.0]


def test_embedder_batch_processing():
    """Custom embedder should handle batch processing correctly."""
    mock = MockEmbedder(dimension=10)

    texts = ["first", "second", "third"]
    results = mock.get_embeddings(texts)

    assert len(results) == 3
    assert results[0] == [5.0] * 10  # "first" = 5 chars
    assert results[1] == [6.0] * 10  # "second" = 6 chars
    assert results[2] == [5.0] * 10  # "third" = 5 chars
    assert mock.call_count == 3  # get_embeddings calls get_embedding internally
