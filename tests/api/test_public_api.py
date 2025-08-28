"""
Tests for public API interface ensuring HRID-only surface and proper functionality.
"""

import os
from pathlib import Path

import pytest

from memg_core.api.public import add_memory, delete_memory, search


class TestPublicAPIInterface:
    """Test public API functions with proper environment setup."""

    @pytest.fixture(autouse=True)
    def setup_environment(self, temp_db_path: str, test_yaml_path: str):
        """Setup environment variables for each test."""
        os.environ["QDRANT_STORAGE_PATH"] = str(Path(temp_db_path) / "qdrant")
        os.environ["KUZU_DB_PATH"] = str(Path(temp_db_path) / "kuzu")
        os.environ["YAML_PATH"] = test_yaml_path

    def test_add_memory_returns_hrid(
        self, predictable_user_id: str, sample_note_data: dict, test_helpers
    ):
        """Test that add_memory returns HRID, not UUID."""
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Should return HRID format
        test_helpers.assert_hrid_format(hrid, "note")

        # Should not be a UUID
        assert not test_helpers._looks_like_uuid(hrid)

    def test_add_memory_different_types(self, predictable_user_id: str, test_helpers):
        """Test adding different memory types returns correct HRID formats."""
        test_cases = [
            ("memo", {"statement": "Test memo"}),
            ("note", {"statement": "Test note", "project": "test"}),
            ("document", {"statement": "Test doc", "details": "Test details"}),
        ]

        for memory_type, payload in test_cases:
            hrid = add_memory(memory_type=memory_type, payload=payload, user_id=predictable_user_id)

            test_helpers.assert_hrid_format(hrid, memory_type)

    def test_search_returns_hrid_only(
        self, predictable_user_id: str, sample_note_data: dict, test_helpers
    ):
        """Test that search results contain HRIDs, not UUIDs."""
        # Add a memory first
        _hrid = add_memory(
            memory_type="note", payload=sample_note_data, user_id=predictable_user_id
        )

        # Search for it
        results = search(query="test", user_id=predictable_user_id, limit=10)

        assert len(results) > 0, "Should find the added memory"

        # Check that results contain no UUIDs
        for result in results:
            test_helpers.assert_no_uuid_exposure(result)

            # Should have HRID in result
            assert hasattr(result, "memory"), "Result should have memory attribute"
            assert hasattr(result.memory, "hrid"), "Memory should have HRID"
            test_helpers.assert_hrid_format(result.memory.hrid, "note")

    def test_delete_memory_accepts_hrid(self, predictable_user_id: str, sample_note_data: dict):
        """Test that delete_memory accepts HRID and works correctly."""
        # Add a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Delete using HRID
        success = delete_memory(hrid=hrid, user_id=predictable_user_id)
        assert success, "Delete should succeed"

        # Verify it's gone
        results = search(query=sample_note_data["statement"], user_id=predictable_user_id, limit=10)

        # Should not find the deleted memory
        found_hrids = [r.memory.hrid for r in results if hasattr(r.memory, "hrid")]
        assert hrid not in found_hrids, "Deleted memory should not be found in search"

    def test_user_isolation_in_api(self, sample_note_data: dict):
        """Test that users can only see their own memories through API."""
        user1 = "test_user_1"
        user2 = "test_user_2"

        # User 1 adds a memory
        hrid1 = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User 2 should not see User 1's memory
        user2_results = search(query=sample_note_data["statement"], user_id=user2, limit=10)

        user2_hrids = [r.memory.hrid for r in user2_results if hasattr(r.memory, "hrid")]
        assert hrid1 not in user2_hrids, "User 2 should not see User 1's memories"

        # User 1 should see their own memory
        user1_results = search(query=sample_note_data["statement"], user_id=user1, limit=10)

        user1_hrids = [r.memory.hrid for r in user1_results if hasattr(r.memory, "hrid")]
        assert hrid1 in user1_hrids, "User 1 should see their own memories"


class TestPublicAPIErrorHandling:
    """Test error handling in public API functions."""

    @pytest.fixture(autouse=True)
    def setup_environment(self, temp_db_path: str, test_yaml_path: str):
        """Setup environment variables for each test."""
        os.environ["QDRANT_STORAGE_PATH"] = str(Path(temp_db_path) / "qdrant")
        os.environ["KUZU_DB_PATH"] = str(Path(temp_db_path) / "kuzu")
        os.environ["YAML_PATH"] = test_yaml_path

    @pytest.mark.unit
    def test_add_memory_invalid_type(self, predictable_user_id: str):
        """Test that invalid memory types raise appropriate errors."""
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError):  # Should raise ProcessingError for invalid types
            add_memory(
                memory_type="invalid_type",
                payload={"statement": "test"},
                user_id=predictable_user_id,
            )

    @pytest.mark.unit
    def test_add_memory_missing_required_fields(self, predictable_user_id: str):
        """Test that missing required fields raise appropriate errors."""
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(
            ProcessingError
        ):  # Should raise ProcessingError for missing required fields
            add_memory(
                memory_type="document",
                payload={"statement": "test"},  # missing required 'details'
                user_id=predictable_user_id,
            )

    @pytest.mark.unit
    def test_delete_nonexistent_memory(self, predictable_user_id: str):
        """Test deleting non-existent memory returns False."""
        success = delete_memory(
            hrid="NOTE_XXX999",  # Non-existent HRID
            user_id=predictable_user_id,
        )
        assert not success, "Deleting non-existent memory should return False"

    def test_delete_other_users_memory(self, sample_note_data: dict):
        """Test that users cannot delete other users' memories."""
        user1 = "test_user_1"
        user2 = "test_user_2"

        # User 1 creates a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User 2 tries to delete it
        success = delete_memory(hrid=hrid, user_id=user2)
        assert not success, "User should not be able to delete other user's memory"

        # Memory should still exist for User 1
        results = search(query=sample_note_data["statement"], user_id=user1, limit=10)
        found_hrids = [r.memory.hrid for r in results if hasattr(r.memory, "hrid")]
        assert hrid in found_hrids, "Memory should still exist after failed deletion"


class TestPublicAPISearchFiltering:
    """Test search filtering and options in public API."""

    @pytest.fixture(autouse=True)
    def setup_environment(self, temp_db_path: str, test_yaml_path: str):
        """Setup environment variables for each test."""
        os.environ["QDRANT_STORAGE_PATH"] = str(Path(temp_db_path) / "qdrant")
        os.environ["KUZU_DB_PATH"] = str(Path(temp_db_path) / "kuzu")
        os.environ["YAML_PATH"] = test_yaml_path

    def test_search_by_memory_type(self, predictable_user_id: str):
        """Test searching with memory type filter."""
        # Add different types of memories
        note_hrid = add_memory(
            memory_type="note",
            payload={"statement": "authentication system note"},
            user_id=predictable_user_id,
        )

        doc_hrid = add_memory(
            memory_type="document",
            payload={
                "statement": "authentication system documentation",
                "details": "Detailed authentication guide",
            },
            user_id=predictable_user_id,
        )

        # Search for notes only
        note_results = search(
            query="authentication", user_id=predictable_user_id, memory_type="note", limit=10
        )

        note_hrids = [r.memory.hrid for r in note_results if hasattr(r.memory, "hrid")]
        assert note_hrid in note_hrids, "Should find note"
        assert doc_hrid not in note_hrids, "Should not find document when filtering for notes"

        # Search for documents only
        doc_results = search(
            query="authentication", user_id=predictable_user_id, memory_type="document", limit=10
        )

        doc_hrids = [r.memory.hrid for r in doc_results if hasattr(r.memory, "hrid")]
        assert doc_hrid in doc_hrids, "Should find document"
        assert note_hrid not in doc_hrids, "Should not find note when filtering for documents"

    def test_search_limit_parameter(self, predictable_user_id: str):
        """Test that search limit parameter works correctly."""
        # Add multiple memories
        hrids = []
        for i in range(5):
            hrid = add_memory(
                memory_type="note",
                payload={"statement": f"test note number {i}"},
                user_id=predictable_user_id,
            )
            hrids.append(hrid)

        # Search with limit
        results = search(query="test note", user_id=predictable_user_id, limit=3)

        assert len(results) <= 3, f"Should return at most 3 results, got {len(results)}"
        assert len(results) > 0, "Should return some results"

    def test_empty_search_query(self, predictable_user_id: str, sample_note_data: dict):
        """Test behavior with empty search query."""
        # Add a memory
        add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Search with empty query
        results = search(query="", user_id=predictable_user_id, limit=10)

        # Should handle empty query gracefully (implementation dependent)
        assert isinstance(results, list), "Should return a list even with empty query"
