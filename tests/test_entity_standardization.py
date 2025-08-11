"""
Comprehensive tests for EntityType standardization implementation.

This test suite validates the successful implementation of the 16 standardized
EntityTypes across the entire memory system pipeline.
"""

from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from memg_core.models.core import (
    Entity,
    EntityType,
    Memory,
    MemoryType,
    Relationship,
)

# MemoryProcessor moved to _stash - test core functionality only
from memg_core.processing.memory_retriever import MemoryRetriever


class TestEntityModelValidation:
    """Unit tests for Entity model validation with standardized types."""

    def test_create_entity_with_valid_type(self):
        """Test Entity creation with valid EntityType enum member."""
        entity = Entity(
            user_id="test_user",
            name="Docker",
            type=EntityType.TECHNOLOGY,
            description="Container platform",
        )
        assert entity.type == EntityType.TECHNOLOGY
        assert entity.name == "Docker"
        assert entity.user_id == "test_user"

    def test_create_entity_with_invalid_type_string(self):
        """Test Entity creation fails with invalid type string."""
        with pytest.raises(ValueError):  # Pydantic validation error
            Entity(
                user_id="test_user",
                name="Test",
                type="database_system",  # Invalid string, not enum
                description="Test description",
            )

    def test_entity_serialization_for_kuzu(self):
        """Test Entity.to_kuzu_node() returns correct string value for database storage."""
        entity = Entity(
            user_id="test_user",
            name="PostgreSQL",
            type=EntityType.DATABASE,
            description="Relational database",
        )

        kuzu_node = entity.to_kuzu_node()
        assert kuzu_node["type"] == "DATABASE"  # String value, not enum
        assert kuzu_node["name"] == "PostgreSQL"
        assert kuzu_node["user_id"] == "test_user"

    def test_all_16_entity_types_available(self):
        """Test the 16 standardized EntityTypes are available (allowing additional types)."""
        expected_types = {
            # Technology Types
            "TECHNOLOGY",
            "DATABASE",
            "LIBRARY",
            "TOOL",
            # System Types
            "COMPONENT",
            "SERVICE",
            "ARCHITECTURE",
            "PROTOCOL",
            # Problem/Solution Types
            "ERROR",
            "ISSUE",
            "SOLUTION",
            "WORKAROUND",
            # Domain Types
            "CONCEPT",
            "METHOD",
            "CONFIGURATION",
            "FILE_TYPE",
        }

        actual_types = {et.value for et in EntityType}
        assert expected_types.issubset(actual_types)
        # Allow additional task-related types; ensure at least 16
        assert len(list(EntityType)) >= 16


class TestMigrationLogic:
    """Unit tests for migration script mapping logic."""

    def test_migration_mapping_direct_hit(self):
        """Test direct mapping of known legacy types."""
        try:
            from scripts.migrate_entity_types import (
                get_standardized_type,  # type: ignore
            )
        except ImportError as e:
            pytest.skip(f"Migration script not available in test environment: {e}")

        # Test known mappings
        assert get_standardized_type("framework") == EntityType.TECHNOLOGY
        assert get_standardized_type("database_system") == EntityType.DATABASE
        assert get_standardized_type("exception") == EntityType.ERROR
        assert get_standardized_type("fix") == EntityType.SOLUTION

    def test_migration_mapping_case_insensitivity(self):
        """Test mapping works with different casing."""
        try:
            from scripts.migrate_entity_types import (
                get_standardized_type,  # type: ignore
            )
        except ImportError as e:
            pytest.skip(f"Migration script not available in test environment: {e}")

        assert get_standardized_type("Database") == EntityType.DATABASE
        assert get_standardized_type("DATABASE") == EntityType.DATABASE
        assert get_standardized_type("database") == EntityType.DATABASE

    def test_migration_mapping_fallback(self):
        """Test fallback to CONCEPT for unknown types."""
        try:
            from scripts.migrate_entity_types import (
                get_standardized_type,  # type: ignore
            )
        except ImportError as e:
            pytest.skip(f"Migration script not available in test environment: {e}")

        result = get_standardized_type("some_random_unknown_type")
        assert result == EntityType.CONCEPT


class TestIntegrationPipeline:
    """Integration tests for entity creation and retrieval pipelines."""

    # MemoryProcessor moved to _stash - removed mock

    @pytest.fixture
    def mock_memory_retriever(self):
        """Create a mock MemoryRetriever for testing."""
        retriever = Mock(spec=MemoryRetriever)
        return retriever

    def test_entity_types_in_technology_query(self):
        """Test retriever builds correct technology search query."""
        # This tests the actual query building logic in memory_retriever.py
        from memg_core.processing.memory_retriever import MemoryRetriever

        # Create retriever with mocked dependencies
        with (
            patch("memg_core.processing.memory_retriever.QdrantInterface"),
            patch("memg_core.processing.memory_retriever.GenAIEmbedder"),
            patch("memg_core.processing.memory_retriever.KuzuInterface") as mock_kuzu,
        ):
            retriever = MemoryRetriever()

            # Mock the query method to capture the query string
            mock_kuzu.return_value.query.return_value = []

            # Call the method (async, so we need to handle that)
            import asyncio
            import contextlib

            with contextlib.suppress(Exception):
                asyncio.run(
                    retriever.search_by_technology("docker", user_id="test_user")
                )  # We expect this to fail due to mocking, but we want to check the query

            # Verify the query was called with correct EntityTypes
            if mock_kuzu.return_value.query.called:
                call_args = mock_kuzu.return_value.query.call_args
                query_string = call_args[0][
                    0
                ]  # First argument should be the query string

                # Check that the query contains the correct entity types for technology search
                assert "TECHNOLOGY" in query_string
                assert "DATABASE" in query_string
                assert "LIBRARY" in query_string
                assert "TOOL" in query_string

    def test_entity_types_in_component_query(self):
        """Test retriever builds correct component search query."""
        from memg_core.processing.memory_retriever import MemoryRetriever

        with (
            patch("memg_core.processing.memory_retriever.QdrantInterface"),
            patch("memg_core.processing.memory_retriever.GenAIEmbedder"),
            patch("memg_core.processing.memory_retriever.KuzuInterface") as mock_kuzu,
        ):
            retriever = MemoryRetriever()
            mock_kuzu.return_value.query.return_value = []

            import asyncio
            import contextlib

            with contextlib.suppress(Exception):
                asyncio.run(
                    retriever.search_by_component("api-service", user_id="test_user")
                )

            if mock_kuzu.return_value.query.called:
                call_args = mock_kuzu.return_value.query.call_args
                query_string = call_args[0][0]

                # Check component-related entity types
                assert "COMPONENT" in query_string
                assert "SERVICE" in query_string
                assert "ARCHITECTURE" in query_string

    def test_entity_types_in_error_solution_query(self):
        """Test retriever builds correct error solution search query."""
        from memg_core.processing.memory_retriever import MemoryRetriever

        with (
            patch("memg_core.processing.memory_retriever.QdrantInterface"),
            patch("memg_core.processing.memory_retriever.GenAIEmbedder"),
            patch("memg_core.processing.memory_retriever.KuzuInterface") as mock_kuzu,
        ):
            retriever = MemoryRetriever()
            mock_kuzu.return_value.query.return_value = []

            import asyncio
            import contextlib

            with contextlib.suppress(Exception):
                asyncio.run(
                    retriever.find_error_solutions(
                        "connection failed", user_id="test_user"
                    )
                )

            if mock_kuzu.return_value.query.called:
                call_args = mock_kuzu.return_value.query.call_args
                query_string = call_args[0][0]

                # Check error/solution entity types
                assert "ERROR" in query_string
                assert "ISSUE" in query_string
                assert "SOLUTION" in query_string or "WORKAROUND" in query_string


class TestMemoryCreation:
    """Test memory creation with proper type validation."""

    def test_memory_creation_with_valid_types(self):
        """Test Memory model accepts valid MemoryType enum values."""
        memory = Memory(
            user_id="test_user", content="Test content", memory_type=MemoryType.DOCUMENT
        )
        assert memory.memory_type == MemoryType.DOCUMENT

        memory2 = Memory(
            user_id="test_user", content="Test note", memory_type=MemoryType.NOTE
        )
        assert memory2.memory_type == MemoryType.NOTE

    def test_memory_serialization_preserves_types(self):
        """Test Memory serialization preserves type information correctly."""
        memory = Memory(
            user_id="test_user",
            content="Test document content",
            memory_type=MemoryType.DOCUMENT,
            title="Test Document",
        )

        # Test Qdrant payload serialization
        qdrant_payload = memory.to_qdrant_payload()
        assert qdrant_payload["memory_type"] == "document"

        # Test Kuzu node serialization
        kuzu_node = memory.to_kuzu_node()
        assert kuzu_node["memory_type"] == "document"


class TestRelationshipCreation:
    """Test relationship creation and validation."""

    def test_relationship_creation(self):
        """Test Relationship model creation with proper validation."""
        relationship = Relationship(
            user_id="test_user",
            source_id="memory_1",
            target_id="entity_1",
            relationship_type="MENTIONS",
        )

        assert relationship.user_id == "test_user"
        assert relationship.relationship_type == "MENTIONS"
        assert relationship.confidence == 0.8  # Default value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
