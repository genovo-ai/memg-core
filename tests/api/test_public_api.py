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
        search_result = search(query="test", user_id=predictable_user_id, limit=10)

        assert len(search_result.memories) > 0, "Should find the added memory"

        # Check that results contain no UUIDs
        test_helpers.assert_no_uuid_exposure(search_result)

        # Check memories (seeds) for HRID format
        for memory_seed in search_result.memories:
            assert hasattr(memory_seed, "hrid"), "Memory seed should have HRID"
            test_helpers.assert_hrid_format(memory_seed.hrid, "note")

        # Check neighbors for HRID format if any exist
        for memory_neighbor in search_result.neighbors:
            assert hasattr(memory_neighbor, "hrid"), "Memory neighbor should have HRID"

    def test_delete_memory_accepts_hrid(self, predictable_user_id: str, sample_note_data: dict):
        """Test that delete_memory accepts HRID and works correctly."""
        # Add a memory
        hrid = add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Delete using HRID
        success = delete_memory(hrid=hrid, user_id=predictable_user_id)
        assert success, "Delete should succeed"

        # Verify it's gone
        search_result = search(
            query=sample_note_data["statement"], user_id=predictable_user_id, limit=10
        )

        # Should not find the deleted memory
        found_hrids = [m.hrid for m in search_result.memories]
        assert hrid not in found_hrids, "Deleted memory should not be found in search"

    def test_user_isolation_in_api(self, sample_note_data: dict):
        """Test that users can only see their own memories through API."""
        user1 = "test_user_1"
        user2 = "test_user_2"

        # User 1 adds a memory
        hrid1 = add_memory(memory_type="note", payload=sample_note_data, user_id=user1)

        # User 2 should not see User 1's memory
        user2_search_result = search(query=sample_note_data["statement"], user_id=user2, limit=10)

        user2_hrids = [m.hrid for m in user2_search_result.memories]
        assert hrid1 not in user2_hrids, "User 2 should not see User 1's memories"

        # User 1 should see their own memory
        user1_search_result = search(query=sample_note_data["statement"], user_id=user1, limit=10)

        user1_hrids = [m.hrid for m in user1_search_result.memories]
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
        found_hrids = [m.hrid for m in results.memories]
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
        note_search_result = search(
            query="authentication",
            user_id=predictable_user_id,
            memory_type="note",
            limit=10,
        )

        note_hrids = [m.hrid for m in note_search_result.memories]
        assert note_hrid in note_hrids, "Should find note"
        assert doc_hrid not in note_hrids, "Should not find document when filtering for notes"

        # Search for documents only
        doc_search_result = search(
            query="authentication",
            user_id=predictable_user_id,
            memory_type="document",
            limit=10,
        )

        doc_hrids = [m.hrid for m in doc_search_result.memories]
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
        search_result = search(query="test note", user_id=predictable_user_id, limit=3)

        # The limit applies to seeds (memories), not total results
        assert len(search_result.memories) <= 3, (
            f"Should return at most 3 memory seeds, got {len(search_result.memories)}"
        )
        assert len(search_result.memories) > 0, "Should return some memory seeds"

    def test_empty_search_query(self, predictable_user_id: str, sample_note_data: dict):
        """Test behavior with empty search query."""
        # Add a memory
        add_memory(memory_type="note", payload=sample_note_data, user_id=predictable_user_id)

        # Search with empty query
        search_result = search(query="", user_id=predictable_user_id, limit=10)

        # Should handle empty query gracefully (implementation dependent)
        assert hasattr(search_result, "memories"), (
            "Should return SearchResult with memories attribute"
        )
        assert hasattr(search_result, "neighbors"), (
            "Should return SearchResult with neighbors attribute"
        )

    def test_decay_filtering_parameters(self, predictable_user_id: str):
        """Test the new decay filtering system with score_threshold, decay_rate, and decay_threshold."""
        # Add memories that will create a connected graph using available test schema types
        task_hrid = add_memory(
            memory_type="task",
            payload={"statement": "implement authentication system", "priority": "high"},
            user_id=predictable_user_id,
        )

        note_hrid = add_memory(
            memory_type="note",
            payload={"statement": "authentication login issue notes", "project": "auth"},
            user_id=predictable_user_id,
        )

        document_hrid = add_memory(
            memory_type="document",
            payload={
                "statement": "authentication system documentation",
                "details": "Detailed auth guide",
            },
            user_id=predictable_user_id,
        )

        # Create relationships to enable graph expansion using available predicates
        add_relationship(
            from_memory_hrid=note_hrid,
            to_memory_hrid=task_hrid,
            relation_type="ANNOTATES",
            from_memory_type="note",
            to_memory_type="task",
            user_id=predictable_user_id,
        )

        add_relationship(
            from_memory_hrid=document_hrid,
            to_memory_hrid=task_hrid,
            relation_type="SUPPORTS",
            from_memory_type="document",
            to_memory_type="task",
            user_id=predictable_user_id,
        )

        # Test 1: Basic search without decay filtering
        basic_result = search(
            query="authentication",
            user_id=predictable_user_id,
            limit=5,
            hops=2,  # Enable graph expansion
        )

        basic_memory_count = len(basic_result.memories)

        assert basic_memory_count > 0, "Should find some memories"

        # Test 2: Search with score_threshold (conservative default)
        threshold_result = search(
            query="authentication",
            user_id=predictable_user_id,
            limit=5,
            hops=2,
            score_threshold=0.1,  # Low threshold to allow most results
        )

        # Should have similar or fewer results due to threshold
        assert len(threshold_result.memories) <= basic_memory_count

        # Test 3: Search with decay_rate (dynamic decay)
        decay_rate_result = search(
            query="authentication",
            user_id=predictable_user_id,
            limit=5,
            hops=2,
            score_threshold=0.1,
            decay_rate=0.5,  # Aggressive decay
        )

        # Should potentially have fewer neighbors due to decay filtering
        assert len(decay_rate_result.memories) <= len(threshold_result.memories)

        # Test 4: Search with explicit decay_threshold
        explicit_threshold_result = search(
            query="authentication",
            user_id=predictable_user_id,
            limit=5,
            hops=2,
            score_threshold=0.1,
            decay_threshold=0.05,  # Very low explicit threshold
        )

        assert len(explicit_threshold_result.memories) <= len(threshold_result.memories)

        # Test 5: Verify API accepts all parameters without error
        comprehensive_result = search(
            query="authentication",
            user_id=predictable_user_id,
            limit=5,
            hops=2,
            score_threshold=0.2,
            decay_rate=0.8,
            decay_threshold=0.1,  # This should override decay_rate calculation
        )

        # Should complete without errors

        assert isinstance(comprehensive_result.memories, list)
        assert isinstance(comprehensive_result.neighbors, list)

    def test_decay_threshold_calculation_logic(self):
        """Test the threshold calculation logic directly."""

        # Create a mock service to test the calculation method
        class MockSearchService:
            def _calculate_neighbor_threshold(
                self, score_threshold, decay_rate, decay_threshold, hops
            ):
                # Copy the exact logic from SearchService
                if decay_threshold is not None:
                    return decay_threshold
                if score_threshold is not None and decay_rate is not None:
                    return score_threshold * (decay_rate**hops)
                if score_threshold is not None:
                    return score_threshold
                return None

        service = MockSearchService()

        # Test case 1: Explicit decay_threshold takes precedence
        result = service._calculate_neighbor_threshold(0.8, 0.9, 0.6, 2)
        assert result == 0.6, f"Expected 0.6, got {result}"

        # Test case 2: Dynamic decay calculation
        result = service._calculate_neighbor_threshold(0.8, 0.9, None, 2)
        expected = 0.8 * (0.9**2)  # 0.648
        assert abs(result - expected) < 0.001, f"Expected {expected}, got {result}"

        # Test case 3: Conservative default (same threshold)
        result = service._calculate_neighbor_threshold(0.8, None, None, 2)
        assert result == 0.8, f"Expected 0.8, got {result}"

        # Test case 4: No filtering
        result = service._calculate_neighbor_threshold(None, None, None, 2)
        assert result is None, f"Expected None, got {result}"

        # Test case 5: Edge case - zero hops
        result = service._calculate_neighbor_threshold(0.8, 0.5, None, 0)
        expected = 0.8 * (0.5**0)  # 0.8 * 1 = 0.8
        assert result == expected, f"Expected {expected}, got {result}"


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
        assert len(results.memories) > 0, "Should find updated memory"

        updated_memory = results.memories[0]
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
        updated_memory = results.memories[0]
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
        search_result = get_memory(hrid=hrid, user_id=predictable_user_id)

        assert search_result is not None, "Should retrieve existing memory"
        assert len(search_result.memories) == 1, "Should have exactly one memory"

        memory_data = search_result.memories[0]
        assert memory_data.hrid == hrid
        assert memory_data.memory_type == "note"
        assert memory_data.user_id == predictable_user_id
        assert memory_data.payload["statement"] == sample_note_data["statement"]

        # Should not expose UUIDs - convert to dict for helper
        memory_dict = memory_data.model_dump()
        test_helpers.assert_no_uuid_exposure(memory_dict)

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
        search_result = get_memories(user_id=predictable_user_id)

        assert len(search_result.memories) >= 2, "Should retrieve all user memories"

        # Check that both memories are present
        hrids = [m.hrid for m in search_result.memories]
        assert note_hrid in hrids, "Should include note"
        assert doc_hrid in hrids, "Should include document"

        # Verify structure
        for memory in search_result.memories:
            assert memory.hrid is not None
            assert memory.memory_type is not None
            assert memory.user_id is not None
            assert memory.payload is not None
            assert memory.user_id == predictable_user_id
            # Convert to dict for helper
            memory_dict = memory.model_dump()
            test_helpers.assert_no_uuid_exposure(memory_dict)

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
        search_result = get_memories(user_id=predictable_user_id, memory_type="note")

        assert len(search_result.memories) >= 1, "Should find at least one note"
        for memory in search_result.memories:
            assert memory.memory_type == "note", "Should only return notes"

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
        search_result = get_memories(user_id=predictable_user_id, limit=3)
        assert len(search_result.memories) <= 3, "Should respect limit"

        # Test offset
        offset_result = get_memories(user_id=predictable_user_id, limit=2, offset=2)
        assert len(offset_result.memories) <= 2, "Should respect limit with offset"

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

        user1_statements = [m.payload["statement"] for m in user1_memories.memories]
        user2_statements = [m.payload["statement"] for m in user2_memories.memories]

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
