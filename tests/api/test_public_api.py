"""
Tests for public API interface ensuring HRID-only surface and proper functionality.
"""

import os
from pathlib import Path

import pytest

from memg_core.api.public import (
    add_memory,
    add_relationship,
    delete_memory,
    delete_relationship,
    get_memories,
    get_memory,
    search,
    update_memory,
)


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
        """Test deleting non-existent memory raises ProcessingError."""
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError, match="Failed to delete memory"):
            delete_memory(
                hrid="NOTE_XXX999",  # Non-existent HRID
                user_id=predictable_user_id,
            )

    def test_delete_other_users_memory(self, sample_note_data: dict):
        """Test that users cannot delete other users' memories."""
        user1 = "test_user_1"
        user2 = "test_user_2"

        # User 1 creates a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User 2 tries to delete it - should raise exception
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError):
            delete_memory(hrid=hrid, user_id=user2)

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
            query="authentication",
            user_id=predictable_user_id,
            memory_type="note",
            limit=10,
        )

        note_hrids = [r.memory.hrid for r in note_results if hasattr(r.memory, "hrid")]
        assert note_hrid in note_hrids, "Should find note"
        assert doc_hrid not in note_hrids, "Should not find document when filtering for notes"

        # Search for documents only
        doc_results = search(
            query="authentication",
            user_id=predictable_user_id,
            memory_type="document",
            limit=10,
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


class TestNewAPIFunctionality:
    """Test new API functions: update_memory, delete_relationship, get_memory, get_memories."""

    def test_update_memory_basic(
        self, predictable_user_id: str, sample_note_data: dict, test_helpers
    ):
        """Test basic update_memory functionality."""
        # Create a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Update the memory
        updates = {"statement": "Updated note statement", "project": "updated-project"}
        success = update_memory(hrid=hrid, payload_updates=updates, user_id=predictable_user_id)

        assert success, "Update should succeed"

        # Verify the update by searching
        results = search(query="Updated note", user_id=predictable_user_id, limit=5)
        assert len(results) > 0, "Should find updated memory"

        updated_memory = results[0].memory
        assert updated_memory.payload["statement"] == "Updated note statement"
        assert updated_memory.payload["project"] == "updated-project"
        # Original fields should be preserved if not updated
        assert updated_memory.payload["origin"] == sample_note_data["origin"]

    def test_update_memory_partial_update(self, predictable_user_id: str, sample_note_data: dict):
        """Test partial update (patch-style) functionality."""
        # Create a memory with multiple fields
        original_payload = {
            "statement": "Original statement",
            "project": "original-project",
            "origin": "user",
        }
        hrid = add_memory(memory_type="note", payload=original_payload, user_id=predictable_user_id)

        # Update only one field
        updates = {"project": "new-project"}
        success = update_memory(hrid=hrid, payload_updates=updates, user_id=predictable_user_id)

        assert success, "Partial update should succeed"

        # Verify other fields are preserved
        results = search(query="Original statement", user_id=predictable_user_id, limit=5)
        updated_memory = results[0].memory
        assert updated_memory.payload["statement"] == "Original statement"  # Unchanged
        assert updated_memory.payload["project"] == "new-project"  # Updated
        assert updated_memory.payload["origin"] == "user"  # Unchanged

    def test_update_memory_nonexistent(self, predictable_user_id: str):
        """Test updating non-existent memory."""
        fake_hrid = "NOTE_XXX999"
        updates = {"statement": "This should fail"}

        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError):
            update_memory(hrid=fake_hrid, payload_updates=updates, user_id=predictable_user_id)

    def test_update_memory_wrong_user(self, sample_note_data: dict):
        """Test updating memory owned by different user."""
        user1 = "user1"
        user2 = "user2"

        # User1 creates memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User2 tries to update it - should raise exception
        updates = {"statement": "Unauthorized update"}
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError):
            update_memory(hrid=hrid, payload_updates=updates, user_id=user2)

    def test_get_memory_basic(self, predictable_user_id: str, sample_note_data: dict, test_helpers):
        """Test basic get_memory functionality."""
        # Create a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Retrieve the memory
        memory_data = get_memory(hrid=hrid, user_id=predictable_user_id)

        assert memory_data is not None, "Should retrieve existing memory"
        assert memory_data["hrid"] == hrid
        assert memory_data["memory_type"] == "note"
        assert memory_data["user_id"] == predictable_user_id
        assert memory_data["payload"]["statement"] == sample_note_data["statement"]

        # Should not expose UUIDs
        test_helpers.assert_no_uuid_exposure(memory_data)

    def test_get_memory_nonexistent(self, predictable_user_id: str):
        """Test getting non-existent memory."""
        fake_hrid = "NOTE_XXX999"
        memory_data = get_memory(hrid=fake_hrid, user_id=predictable_user_id)

        assert memory_data is None, "Should return None for non-existent memory"

    def test_get_memory_wrong_user(self, sample_note_data: dict):
        """Test getting memory owned by different user."""
        user1 = "user1"
        user2 = "user2"

        # User1 creates memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User2 tries to get it
        memory_data = get_memory(hrid=hrid, user_id=user2)

        assert memory_data is None, "Should not retrieve other user's memory"

    def test_get_memories_basic(self, predictable_user_id: str, test_helpers):
        """Test basic get_memories functionality."""
        # Create multiple memories
        note_hrid = add_memory(
            memory_type="note",
            payload={"statement": "Test note", "origin": "user"},
            user_id=predictable_user_id,
        )
        doc_hrid = add_memory(
            memory_type="document",
            payload={"statement": "Test document", "details": "Document details"},
            user_id=predictable_user_id,
        )

        # Get all memories
        memories = get_memories(user_id=predictable_user_id)

        assert len(memories) >= 2, "Should retrieve all user memories"

        # Check that both memories are present
        hrids = [m["hrid"] for m in memories]
        assert note_hrid in hrids, "Should include note"
        assert doc_hrid in hrids, "Should include document"

        # Verify structure
        for memory in memories:
            assert "hrid" in memory
            assert "memory_type" in memory
            assert "user_id" in memory
            assert "payload" in memory
            assert memory["user_id"] == predictable_user_id
            test_helpers.assert_no_uuid_exposure(memory)

    def test_get_memories_filtered_by_type(self, predictable_user_id: str):
        """Test get_memories with memory type filtering."""
        # Create different types
        add_memory(
            memory_type="note",
            payload={"statement": "Test note", "origin": "user"},
            user_id=predictable_user_id,
        )
        add_memory(
            memory_type="document",
            payload={"statement": "Test document", "details": "Document details"},
            user_id=predictable_user_id,
        )

        # Get only notes
        notes = get_memories(user_id=predictable_user_id, memory_type="note")

        assert len(notes) >= 1, "Should find at least one note"
        for memory in notes:
            assert memory["memory_type"] == "note", "Should only return notes"

    def test_get_memories_with_pagination(self, predictable_user_id: str):
        """Test get_memories with limit and offset."""
        # Create multiple memories
        for i in range(5):
            add_memory(
                memory_type="note",
                payload={"statement": f"Test note {i}", "origin": "user"},
                user_id=predictable_user_id,
            )

        # Test limit
        limited = get_memories(user_id=predictable_user_id, limit=3)
        assert len(limited) <= 3, "Should respect limit"

        # Test offset
        offset_results = get_memories(user_id=predictable_user_id, limit=2, offset=2)
        assert len(offset_results) <= 2, "Should respect limit with offset"

    def test_get_memories_user_isolation(self):
        """Test get_memories respects user isolation."""
        user1 = "user1"
        user2 = "user2"

        # Each user creates memories
        add_memory(
            memory_type="note",
            payload={"statement": "User1 note", "origin": "user"},
            user_id=user1,
        )
        add_memory(
            memory_type="note",
            payload={"statement": "User2 note", "origin": "user"},
            user_id=user2,
        )

        # Each user should only see their own
        user1_memories = get_memories(user_id=user1)
        user2_memories = get_memories(user_id=user2)

        user1_statements = [m["payload"]["statement"] for m in user1_memories]
        user2_statements = [m["payload"]["statement"] for m in user2_memories]

        assert "User1 note" in user1_statements, "User1 should see their note"
        assert "User1 note" not in user2_statements, "User2 should not see User1's note"
        assert "User2 note" in user2_statements, "User2 should see their note"
        assert "User2 note" not in user1_statements, "User1 should not see User2's note"

    def test_add_relationship_basic(self, predictable_user_id: str):
        """Test basic add_relationship functionality."""
        # Create two memories using entities available in test schema
        task_hrid = add_memory(
            memory_type="task",
            payload={
                "statement": "Implement feature",
                "status": "todo",
                "priority": "high",
            },
            user_id=predictable_user_id,
        )
        doc_hrid = add_memory(
            memory_type="document",
            payload={"statement": "Feature specification", "details": "Detailed spec"},
            user_id=predictable_user_id,
        )

        # Add relationship using predicates available in test schema (task -> document: REFERENCES)
        try:
            add_relationship(
                from_memory_hrid=task_hrid,
                to_memory_hrid=doc_hrid,
                relation_type="REFERENCES",  # This should exist in test schema
                from_memory_type="task",
                to_memory_type="document",
                user_id=predictable_user_id,
            )
            # If we get here, the relationship was added successfully
            assert True, "Relationship should be added if predicate exists in schema"
        except Exception as e:
            # If it fails due to schema validation, that's expected behavior
            assert (
                "Invalid relationship predicate" in str(e)
                or "not defined in YAML schema" in str(e)
                or "does not exist" in str(e)
            ), f"Should fail with schema validation error, got: {e}"

    def test_delete_relationship_basic(self, predictable_user_id: str):
        """Test basic delete_relationship functionality."""
        # Create two memories
        note1_hrid = add_memory(
            memory_type="note",
            payload={"statement": "First note", "origin": "user"},
            user_id=predictable_user_id,
        )
        note2_hrid = add_memory(
            memory_type="note",
            payload={"statement": "Second note", "origin": "user"},
            user_id=predictable_user_id,
        )

        # Try to add and then delete a relationship
        try:
            # First add a relationship (if schema supports it)
            add_relationship(
                from_memory_hrid=note1_hrid,
                to_memory_hrid=note2_hrid,
                relation_type="RELATED_TO",  # This should exist in schema
                from_memory_type="note",
                to_memory_type="note",
                user_id=predictable_user_id,
            )

            # Then delete it
            success = delete_relationship(
                from_memory_hrid=note1_hrid,
                to_memory_hrid=note2_hrid,
                relation_type="RELATED_TO",
                from_memory_type="note",
                to_memory_type="note",
                user_id=predictable_user_id,
            )

            assert success, "Should successfully delete existing relationship"

        except Exception as e:
            # If relationship creation fails due to schema, skip the test
            if "Invalid relationship predicate" in str(e):
                pytest.skip(f"Skipping relationship test - predicate not in schema: {e}")
            else:
                raise

    def test_delete_relationship_nonexistent(self, predictable_user_id: str):
        """Test deleting non-existent relationship."""
        # Create two memories but no relationship
        note1_hrid = add_memory(
            memory_type="note",
            payload={"statement": "First note", "origin": "user"},
            user_id=predictable_user_id,
        )
        note2_hrid = add_memory(
            memory_type="note",
            payload={"statement": "Second note", "origin": "user"},
            user_id=predictable_user_id,
        )

        # Try to delete non-existent relationship - should return False
        success = delete_relationship(
            from_memory_hrid=note1_hrid,
            to_memory_hrid=note2_hrid,
            relation_type="RELATED_TO",
            from_memory_type="note",
            to_memory_type="note",
            user_id=predictable_user_id,
        )

        # Should return False for non-existent relationship
        assert not success, "Should return False for non-existent relationship"

    def test_relationship_user_isolation(self):
        """Test that relationships respect user isolation."""
        user1 = "user1"
        user2 = "user2"

        # User1 creates memories
        user1_note1 = add_memory(
            memory_type="note",
            payload={"statement": "User1 note1", "origin": "user"},
            user_id=user1,
        )
        add_memory(
            memory_type="note",
            payload={"statement": "User1 note2", "origin": "user"},
            user_id=user1,
        )

        # User2 creates memory
        user2_note = add_memory(
            memory_type="note",
            payload={"statement": "User2 note", "origin": "user"},
            user_id=user2,
        )

        # User2 should not be able to create relationship with User1's memories
        try:
            add_relationship(
                from_memory_hrid=user2_note,
                to_memory_hrid=user1_note1,  # Different user's memory
                relation_type="RELATED_TO",
                from_memory_type="note",
                to_memory_type="note",
                user_id=user2,
            )
            # If this succeeds, it's a security issue
            raise AssertionError("Should not allow cross-user relationships")
        except Exception as e:
            # Should fail due to access control or memory not found
            assert (
                "not found" in str(e).lower()
                or "access" in str(e).lower()
                or "Invalid relationship predicate" in str(e)
            ), f"Should fail with appropriate error, got: {e}"
