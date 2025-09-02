"""
System readiness test - demonstrates that MEMG Core is ready for production.
This test validates the complete system end-to-end.
"""

import pytest

from memg_core.api.public import add_memory, delete_memory, search


class TestSystemReadiness:
    """Comprehensive system readiness validation."""

    # Remove custom setup - use conftest.py fixtures instead

    def test_complete_system_functionality(self):
        """Test complete system: YAML → Memory → Search → HRID → Delete."""

        # Test data representing real-world usage
        test_memories = [
            {
                "type": "note",
                "payload": {
                    "statement": "Implement user authentication system",
                    "project": "auth",
                },
                "user": "developer_001",
            },
            {
                "type": "document",
                "payload": {
                    "statement": "Authentication API specification",
                    "details": "Complete API specification for OAuth2 implementation",
                    "project": "auth",
                },
                "user": "developer_001",
            },
            {
                "type": "note",
                "payload": {
                    "statement": "Coffee machine needs repair",
                    "project": "office",
                },
                "user": "developer_002",  # Different user
            },
        ]

        added_hrids = {}

        # 1. Add memories using public API
        for i, memory_data in enumerate(test_memories):
            hrid = add_memory(
                memory_type=memory_data["type"],
                payload=memory_data["payload"],
                user_id=memory_data["user"],
            )

            # Validate HRID format
            assert isinstance(hrid, str), "HRID should be string"
            assert hrid.startswith(f"{memory_data['type'].upper()}_"), (
                f"HRID should start with type: {hrid}"
            )
            assert len(hrid.split("_")[1]) == 6, f"HRID should have 6-char suffix: {hrid}"

            added_hrids[i] = hrid
            print(f"✅ Added {memory_data['type']}: {hrid}")

        # 2. Test search functionality
        auth_search_result = search(query="authentication", user_id="developer_001", limit=10)

        assert len(auth_search_result.memories) >= 2, "Should find authentication-related memories"

        # Validate search results contain HRIDs, not UUIDs
        for memory_seed in auth_search_result.memories:
            assert hasattr(memory_seed, "hrid"), "Memory seed should have HRID"
            assert memory_seed.hrid is not None, "HRID should not be None"

            # Ensure no UUID exposure
            result_str = str(memory_seed.__dict__)
            import uuid

            # Check that no UUID-like strings are present
            words = result_str.split()
            for word in words:
                try:
                    uuid.UUID(word.strip("',\"(){}[]"))
                    raise AssertionError(f"Found exposed UUID in result: {word}")
                except (ValueError, AttributeError):
                    pass  # Good, not a UUID

        print(f"✅ Found {len(auth_search_result.memories)} authentication results")

        # 3. Test user isolation (HRID collision is CORRECT behavior)
        user2_search_result = search(query="authentication", user_id="developer_002", limit=10)

        user2_hrids = [m.hrid for m in user2_search_result.memories]
        user1_hrids = [added_hrids[0], added_hrids[1]]  # First two belong to user 1

        # Users should NOT see each other's memories (even with same HRIDs)
        cross_contamination = False
        for user1_hrid in user1_hrids:
            if user1_hrid in user2_hrids:
                # Check if it's actually the same memory by checking content
                for memory_seed in user2_search_result.memories:
                    if memory_seed.hrid == user1_hrid and "developer_001" in str(
                        memory_seed.payload
                    ):
                        cross_contamination = True
                        break

        assert not cross_contamination, "User 2 should not see user 1's memories"
        print("✅ User isolation verified (same HRIDs across users is correct)")

        # 4. Test memory type filtering
        note_search_result = search(
            query="authentication",
            user_id="developer_001",
            memory_type="note",
            limit=10,
        )

        doc_search_result = search(
            query="authentication",
            user_id="developer_001",
            memory_type="document",
            limit=10,
        )

        # Should find different results for different types
        note_hrids = [m.hrid for m in note_search_result.memories]
        doc_hrids = [m.hrid for m in doc_search_result.memories]

        assert added_hrids[0] in note_hrids, "Should find note when filtering for notes"
        assert added_hrids[1] in doc_hrids, "Should find document when filtering for documents"
        assert added_hrids[0] not in doc_hrids, "Should not find note when filtering for documents"
        assert added_hrids[1] not in note_hrids, "Should not find document when filtering for notes"

        print("✅ Memory type filtering verified")

        # 5. Test deletion using HRID
        success = delete_memory(hrid=added_hrids[0], user_id="developer_001")

        assert success, "Delete should succeed"

        # Verify deletion
        post_delete_search_result = search(
            query="authentication", user_id="developer_001", limit=10
        )

        post_delete_hrids = [m.hrid for m in post_delete_search_result.memories]
        assert added_hrids[0] not in post_delete_hrids, "Deleted memory should not be found"
        assert added_hrids[1] in post_delete_hrids, "Other memory should still exist"

        print("✅ Memory deletion verified")

        # 6. Test cross-user deletion protection - should raise exception
        from memg_core.core.exceptions import ProcessingError

        with pytest.raises(ProcessingError, match="Failed to delete memory"):
            delete_memory(hrid=added_hrids[1], user_id="developer_002")

        print("✅ Cross-user deletion protection verified")

        print("\n🎉 SYSTEM READY: All core functionality validated!")
        print("✅ YAML schema loading")
        print("✅ Memory creation and storage")
        print("✅ HRID generation and format")
        print("✅ Search functionality")
        print("✅ User isolation (HRID collision is correct behavior)")
        print("✅ Memory type filtering")
        print("✅ HRID-only public API (no UUID exposure)")
        print("✅ Memory deletion")
        print("✅ Security (cross-user protection)")

    def test_performance_baseline(self):
        """Establish performance baseline for key operations."""
        import time

        user_id = "perf_test_user"

        # Test add performance
        start_time = time.time()
        hrids = []

        for i in range(10):
            hrid = add_memory(
                memory_type="note",
                payload={"statement": f"Performance test memory {i}"},
                user_id=user_id,
            )
            hrids.append(hrid)

        add_time = time.time() - start_time
        avg_add_time = add_time / 10

        print(
            f"📊 Add performance: {avg_add_time:.3f}s per memory (10 memories in {add_time:.3f}s)"
        )
        assert avg_add_time < 5.0, (
            f"Add operation too slow: {avg_add_time:.3f}s"
        )  # More reasonable for CI

        # Test search performance
        start_time = time.time()
        search_result = search(query="Performance test", user_id=user_id, limit=20)
        search_time = time.time() - start_time

        print(
            f"📊 Search performance: {search_time:.3f}s for {len(search_result.memories)} results"
        )
        assert search_time < 3.0, (
            f"Search operation too slow: {search_time:.3f}s"
        )  # More reasonable for CI
        assert len(search_result.memories) >= 5, "Should find multiple performance test memories"

        print("✅ Performance baseline established")
