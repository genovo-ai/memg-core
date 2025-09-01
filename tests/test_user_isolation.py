"""
Test user isolation and data privacy in the memory system.
"""

from memg_core.api.public import add_memory, delete_memory, search


class TestUserIsolation:
    """Test that users can only access their own data."""

    # Remove custom setup - use conftest.py fixtures instead

    def test_search_data_isolation(self):
        """Test that search results are properly isolated by user."""
        # Add memories for different users
        add_memory(
            memory_type="note",
            payload={"statement": "user1 private information"},
            user_id="test_user_1",
        )

        add_memory(
            memory_type="note",
            payload={"statement": "user2 private information"},
            user_id="test_user_2",
        )

        # Each user should only see their own data
        user1_results = search("private information", "test_user_1", limit=10)
        user2_results = search("private information", "test_user_2", limit=10)

        user1_statements = [r.memory.payload["statement"] for r in user1_results]
        user2_statements = [r.memory.payload["statement"] for r in user2_results]

        assert "user1 private information" in user1_statements
        assert "user2 private information" not in user1_statements
        assert "user2 private information" in user2_statements
        assert "user1 private information" not in user2_statements

    def test_deletion_access_control(self):
        """Test that users can only delete their own memories."""
        # Add memory for user1
        user1_hrid = add_memory(
            memory_type="note",
            payload={"statement": "user1 data to protect"},
            user_id="test_user_1",
        )

        # User1 should be able to delete their own memory
        user1_delete_success = delete_memory(user1_hrid, "test_user_1")
        assert user1_delete_success, "User should be able to delete their own memory"

        # Add another memory for user1
        user1_hrid2 = add_memory(
            memory_type="note",
            payload={"statement": "user1 second data"},
            user_id="test_user_1",
        )

        # User2 should NOT be able to delete user1's memory - should raise exception
        import pytest

        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError, match="Failed to delete memory"):
            delete_memory(user1_hrid2, "test_user_2")

        # Verify memory still exists for user1
        user1_results = search("user1 second data", "test_user_1", limit=10)
        assert len(user1_results) > 0, "Memory should still exist for original user"

    def test_hrid_scoping_per_user(self):
        """Test that HRID mappings are properly scoped per user."""
        # Add memories for different users (may get same HRID - this is correct)
        add_memory(
            memory_type="note",
            payload={"statement": "user1 note content"},
            user_id="test_user_1",
        )

        add_memory(
            memory_type="note",
            payload={"statement": "user2 note content"},
            user_id="test_user_2",
        )

        # Each user should only see their own content
        user1_results = search("note content", "test_user_1", limit=10)
        user2_results = search("note content", "test_user_2", limit=10)

        assert len(user1_results) == 1, "User1 should see exactly 1 result"
        assert len(user2_results) == 1, "User2 should see exactly 1 result"

        user1_content = user1_results[0].memory.payload["statement"]
        user2_content = user2_results[0].memory.payload["statement"]

        assert user1_content == "user1 note content"
        assert user2_content == "user2 note content"

    def test_memory_type_filtering_with_isolation(self):
        """Test memory type filtering works correctly with user isolation."""
        # Add different memory types for different users
        user1_note = add_memory(
            memory_type="note",
            payload={"statement": "user1 note about testing"},
            user_id="test_user_1",
        )

        user1_doc = add_memory(
            memory_type="document",
            payload={
                "statement": "user1 document about testing",
                "details": "detailed info",
            },
            user_id="test_user_1",
        )

        user2_note = add_memory(
            memory_type="note",
            payload={"statement": "user2 note about testing"},
            user_id="test_user_2",
        )

        # Search for notes only as user1
        user1_notes = search("testing", "test_user_1", memory_type="note", limit=10)
        user1_note_hrids = [r.memory.hrid for r in user1_notes]

        assert user1_note in user1_note_hrids, "User1 should see their note"
        assert user1_doc not in user1_note_hrids, (
            "User1 should not see their document in note search"
        )
        assert user2_note not in user1_note_hrids, "User1 should not see user2's note"

    def test_comprehensive_multi_user_isolation(self):
        """Test comprehensive isolation across multiple users and memory types."""
        users = ["alpha_user", "beta_user", "gamma_user"]
        memory_types = ["note", "document"]

        created_memories = {}

        # Create memories for each user
        for user in users:
            created_memories[user] = {}
            for mem_type in memory_types:
                if mem_type == "note":
                    payload = {"statement": f"{user} {mem_type} isolation test"}
                else:  # document
                    payload = {
                        "statement": f"{user} {mem_type} isolation test",
                        "details": f"details for {user}",
                    }

                hrid = add_memory(mem_type, payload, user)
                created_memories[user][mem_type] = hrid

        # Verify each user sees only their own data
        for user in users:
            results = search("isolation test", user, limit=20)

            # Should see exactly 2 results (1 note + 1 document)
            assert len(results) == 2, f"User {user} should see exactly 2 results"

            # Verify all results belong to this user
            for result in results:
                statement = result.memory.payload["statement"]
                assert statement.startswith(user), f"User {user} should only see their own data"

            # Verify no cross-contamination
            for other_user in users:
                if other_user != user:
                    for result in results:
                        statement = result.memory.payload["statement"]
                        assert not statement.startswith(other_user), (
                            f"User {user} should not see {other_user}'s data"
                        )

    def test_edge_cases_user_isolation(self):
        """Test edge cases for user isolation."""

        # Test with similar but different user IDs
        similar_users = ["user_test", "user_test_2", "user_test_admin"]

        for i, user in enumerate(similar_users):
            add_memory(
                memory_type="note",
                payload={"statement": f"data for {user} number {i}"},
                user_id=user,
            )

        # Each user should only see their own data
        for i, user in enumerate(similar_users):
            results = search("data for", user, limit=10)
            assert len(results) == 1, f"User {user} should see exactly 1 result"

            statement = results[0].memory.payload["statement"]
            assert statement == f"data for {user} number {i}", (
                f"User {user} should see their own data"
            )

        # Test with special characters in user_id
        special_user = "user_with_special!@#$%"
        add_memory(
            memory_type="note",
            payload={"statement": "special character test"},
            user_id=special_user,
        )

        special_results = search("special character", special_user, limit=10)
        assert len(special_results) == 1, "Special character user_id should work"

        # Other users should not see special user's data
        normal_results = search("special character", "normal_user", limit=10)
        assert len(normal_results) == 0, "Normal user should not see special user's data"
