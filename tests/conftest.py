"""
Shared test configuration and fixtures for MEMG Core test suite.
"""

from collections.abc import Generator
import os
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch
import uuid

import pytest

from memg_core.core.pipelines.indexer import create_memory_service
from memg_core.core.pipelines.retrieval import create_search_service
from memg_core.utils.db_clients import DatabaseClients


@pytest.fixture
def test_yaml_path() -> str:
    """Path to test YAML schema."""
    return "config/core.test.yaml"


@pytest.fixture
def predictable_user_id(request) -> str:
    """Generate predictable user ID for chainable tests."""
    # Use test name to create predictable but unique user ID
    test_name = request.node.name
    return f"user_{hash(test_name) % 1000:03d}"


@pytest.fixture
def temp_db_path(request) -> Generator[str, None, None]:
    """Create clean database directory with predictable path for debugging."""
    # Create predictable path for easier debugging
    test_name = request.node.name.replace("::", "_").replace("[", "_").replace("]", "")
    base_dir = Path(tempfile.gettempdir()) / "memg_tests" / test_name

    # Clean up any existing test data
    if base_dir.exists():
        import shutil

        shutil.rmtree(base_dir)

    base_dir.mkdir(parents=True, exist_ok=True)

    try:
        yield str(base_dir)
    finally:
        # Clean up after test
        if base_dir.exists():
            import shutil

            shutil.rmtree(base_dir, ignore_errors=True)


@pytest.fixture
def db_clients(test_yaml_path: str, temp_db_path: str) -> Generator[DatabaseClients, None, None]:
    """Create isolated database clients for testing."""
    # Set environment variables for test databases
    os.environ["QDRANT_STORAGE_PATH"] = str(Path(temp_db_path) / "qdrant")
    os.environ["KUZU_DB_PATH"] = str(Path(temp_db_path) / "kuzu")

    # Create database clients
    db_clients = DatabaseClients(yaml_path=test_yaml_path)
    db_clients.init_dbs(db_path=temp_db_path, db_name="test_memg")

    try:
        yield db_clients
    finally:
        # Cleanup
        db_clients.close()


@pytest.fixture
def memory_service(db_clients: DatabaseClients):
    """Create memory service for testing."""
    return create_memory_service(db_clients)


@pytest.fixture
def search_service(db_clients: DatabaseClients):
    """Create search service for testing."""
    return create_search_service(db_clients)


@pytest.fixture
def sample_memo_data() -> dict:
    """Sample memo data for testing."""
    return {"statement": "This is a test memo for validation"}


@pytest.fixture
def sample_note_data() -> dict:
    """Sample note data for testing."""
    return {
        "statement": "Test note about system behavior",
        "project": "memg-core",
        "origin": "system",
    }


@pytest.fixture
def sample_document_data() -> dict:
    """Sample document data for testing."""
    return {
        "statement": "Test documentation for API",
        "details": "Comprehensive guide explaining the test API functionality and usage patterns",
        "project": "memg-core",
        "url": "https://example.com/docs/test-api",
    }


# Performance timing helper
@pytest.fixture
def performance_timer():
    """Helper for timing operations when needed."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None

        def start(self):
            self.start_time = time.time()

        def elapsed(self) -> float:
            if self.start_time is None:
                return 0.0
            return time.time() - self.start_time

        def log_if_slow(self, operation: str, threshold: float = 1.0):
            """Log timing if operation took longer than threshold."""
            elapsed = self.elapsed()
            if elapsed > threshold:
                print(f"⚠️  Slow operation: {operation} took {elapsed:.2f}s")
            return elapsed

    return Timer()


# Test data collections for search accuracy testing (30 memories with variations)
@pytest.fixture
def search_test_data() -> list[dict]:
    """30 test memories with variations and exact duplicates for search testing."""
    return [
        # Cluster 1: Authentication (exact duplicates to test ranking)
        {"type": "note", "payload": {"statement": "user authentication system"}},
        {
            "type": "document",
            "payload": {
                "statement": "user authentication system",
                "details": "Same statement, different type",
            },
        },
        {
            "type": "note",
            "payload": {
                "statement": "authentication system for users",
                "project": "auth",
            },
        },
        {
            "type": "note",
            "payload": {"statement": "login authentication flow", "project": "auth"},
        },
        {
            "type": "document",
            "payload": {
                "statement": "OAuth2 authentication guide",
                "details": "Complete OAuth2 implementation",
            },
        },
        # Cluster 2: Database (semantic variations)
        {"type": "note", "payload": {"statement": "database optimization techniques"}},
        {"type": "note", "payload": {"statement": "database performance tuning"}},
        {
            "type": "document",
            "payload": {
                "statement": "database schema design",
                "details": "Schema design principles",
            },
        },
        {"type": "note", "payload": {"statement": "SQL query optimization"}},
        {
            "type": "document",
            "payload": {
                "statement": "database indexing strategies",
                "details": "Index optimization guide",
            },
        },
        # Cluster 3: API Design (related concepts)
        {"type": "note", "payload": {"statement": "REST API design patterns"}},
        {
            "type": "document",
            "payload": {
                "statement": "API documentation standards",
                "details": "Documentation best practices",
            },
        },
        {"type": "note", "payload": {"statement": "GraphQL API implementation"}},
        {"type": "note", "payload": {"statement": "API rate limiting strategies"}},
        {
            "type": "document",
            "payload": {
                "statement": "API versioning guidelines",
                "details": "Version management approaches",
            },
        },
        # Cluster 4: Security (overlaps with auth)
        {"type": "note", "payload": {"statement": "security best practices"}},
        {"type": "note", "payload": {"statement": "application security measures"}},
        {
            "type": "document",
            "payload": {
                "statement": "security audit checklist",
                "details": "Comprehensive security review",
            },
        },
        {"type": "note", "payload": {"statement": "data encryption methods"}},
        {
            "type": "document",
            "payload": {
                "statement": "security compliance requirements",
                "details": "Regulatory compliance guide",
            },
        },
        # Cluster 5: Unrelated office content (true negatives)
        {
            "type": "note",
            "payload": {"statement": "coffee machine maintenance schedule"},
        },
        {"type": "note", "payload": {"statement": "office parking assignments"}},
        {
            "type": "document",
            "payload": {
                "statement": "holiday calendar 2024",
                "details": "Company holiday schedule",
            },
        },
        {"type": "note", "payload": {"statement": "lunch catering options"}},
        {
            "type": "document",
            "payload": {
                "statement": "office supply inventory",
                "details": "Current office supply status",
            },
        },
        # Cluster 6: Mixed technical (edge cases)
        {"type": "memo", "payload": {"statement": "system architecture overview"}},
        {"type": "memo", "payload": {"statement": "performance monitoring setup"}},
        {"type": "note", "payload": {"statement": "error handling patterns"}},
        {"type": "note", "payload": {"statement": "logging configuration"}},
        {
            "type": "document",
            "payload": {
                "statement": "deployment procedures",
                "details": "Step-by-step deployment guide",
            },
        },
    ]


class TestHelpers:
    """Helper methods for test assertions and validation."""

    @staticmethod
    def assert_hrid_format(hrid: str, expected_type: str) -> None:
        """Assert HRID follows correct format: TYPE_XXX###"""
        assert isinstance(hrid, str), f"HRID should be string, got {type(hrid)}"
        assert hrid.startswith(f"{expected_type.upper()}_"), (
            f"HRID {hrid} should start with {expected_type.upper()}_"
        )

        # Check format: TYPE_XXX### (3 letters + 3 digits)
        parts = hrid.split("_")
        assert len(parts) == 2, f"HRID {hrid} should have format TYPE_XXX###"

        suffix = parts[1]
        assert len(suffix) == 6, f"HRID suffix should be 6 chars, got {len(suffix)} in {hrid}"
        assert suffix[:3].isalpha(), f"HRID should have 3 letters, got {suffix[:3]} in {hrid}"
        assert suffix[3:].isdigit(), f"HRID should have 3 digits, got {suffix[3:]} in {hrid}"

    @staticmethod
    def assert_no_uuid_exposure(data: any) -> None:
        """Assert that no UUIDs are exposed in data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                assert key != "id", f"UUID field 'id' should not be exposed: {key}={value}"
                assert not (isinstance(value, str) and TestHelpers._looks_like_uuid(value)), (
                    f"Value looks like UUID and should not be exposed: {key}={value}"
                )
                TestHelpers.assert_no_uuid_exposure(value)
        elif isinstance(data, (list, tuple)):
            for item in data:
                TestHelpers.assert_no_uuid_exposure(item)

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        """Check if string looks like a UUID."""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False


@pytest.fixture
def test_helpers() -> TestHelpers:
    """Provide test helper methods."""
    return TestHelpers()


@pytest.fixture(autouse=True)
def setup_test_environment(test_yaml_path: str, temp_db_path: str):
    """Set up environment variables required by the refactored public API."""
    # Store original values
    original_yaml = os.environ.get("MEMG_YAML_PATH")
    original_db = os.environ.get("MEMG_DB_PATH")

    # Set test environment variables
    os.environ["MEMG_YAML_PATH"] = test_yaml_path
    os.environ["MEMG_DB_PATH"] = temp_db_path

    try:
        yield
    finally:
        # Shutdown singleton client to prevent connection reuse issues
        from memg_core.api.public import shutdown_services

        shutdown_services()

        # Restore original values
        if original_yaml is not None:
            os.environ["MEMG_YAML_PATH"] = original_yaml
        else:
            os.environ.pop("MEMG_YAML_PATH", None)

        if original_db is not None:
            os.environ["MEMG_DB_PATH"] = original_db
        else:
            os.environ.pop("MEMG_DB_PATH", None)


@pytest.fixture(autouse=True)
def mock_embedder():
    """Mock the embedder to avoid external dependencies and rate limits."""
    mock_embedder = Mock()
    # Return a consistent fake embedding vector
    mock_embedder.get_embedding.return_value = [0.1] * 384  # 384-dim vector like snowflake model

    # Patch both the Embedder class and the get_embedder method
    with (
        patch("memg_core.core.interfaces.embedder.Embedder", return_value=mock_embedder),
        patch(
            "memg_core.utils.db_clients.DatabaseClients.get_embedder",
            return_value=mock_embedder,
        ),
    ):
        yield mock_embedder
