# MEMG Core Tests

This directory contains tests for the MEMG Core system.

## Test Structure

Tests are organized into the following categories:

- **Unit Tests**: Test individual functions and classes in isolation
- **Adapter Tests**: Test interfaces to external systems (Qdrant, Kuzu)
- **Pipeline Tests**: Test the indexing and retrieval pipelines
- **API Tests**: Test the public API contract
- **Lifecycle Tests**: Test memory lifecycle operations
- **Edge Cases**: Test edge cases and regression scenarios
- **Integration Tests**: Test with real external services (marked with `@pytest.mark.integration`)
- **Plugin Tests**: Test plugin optionality

## Running Tests

To run all tests:

```bash
pytest
```

To run tests by category:

```bash
# Run only unit tests
pytest -m unit

# Run only API tests
pytest -m api

# Skip integration tests
pytest -m "not integration"
```

## Test Fixtures

The `conftest.py` file contains test fixtures and test doubles:

- `DummyEmbedder`: Deterministic embedder for testing
- `FakeQdrant`: In-memory Qdrant implementation
- `FakeKuzu`: In-memory Kuzu implementation
- `mem_factory`: Factory for creating Memory objects with defaults
- `tmp_env`: Fixture for temporarily setting environment variables
- `neighbor_cap`: Constant for neighbor cap in tests

## Test Doubles

The test doubles are designed to mimic the behavior of the real systems without external dependencies:

- `DummyEmbedder` generates deterministic vectors based on content hash
- `FakeQdrant` implements vector search with cosine similarity
- `FakeKuzu` implements basic graph operations and queries

## Integration Tests

Integration tests require:

- `GOOGLE_API_KEY` environment variable for GenAI embeddings
- `QDRANT_STORAGE_PATH` environment variable for Qdrant storage
- `KUZU_DB_PATH` environment variable for Kuzu database

These tests are marked with `@pytest.mark.integration` and can be skipped with `-m "not integration"`.
