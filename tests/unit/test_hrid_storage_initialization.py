"""Test HRID storage initialization to prevent collisions after server restarts."""

from unittest.mock import MagicMock

import pytest

from memg_core.utils.hrid import (
    StorageQueryInterface,
    _initialize_counter_from_storage,
    generate_hrid,
    reset_counters,
)

pytestmark = pytest.mark.unit


class MockStorage:
    """Mock storage that implements StorageQueryInterface for testing."""

    def __init__(self, existing_memories=None):
        self.existing_memories = existing_memories or []

    def search_points(self, vector, limit=5, collection=None, user_id=None, filters=None):
        """Mock search that returns filtered results based on memory_type filter."""
        if not filters or "core.memory_type" not in filters:
            return self.existing_memories

        memory_type_filter = filters["core.memory_type"]
        filtered = []

        for memory in self.existing_memories:
            payload = memory.get("payload", {})
            core = payload.get("core", {})
            # Case-insensitive comparison for memory type
            stored_type = core.get("memory_type", "").upper()
            filter_type = memory_type_filter.upper()
            if stored_type == filter_type:
                filtered.append(memory)

        return filtered[:limit]


def create_mock_memory(memory_type, hrid):
    """Helper to create mock memory with specific HRID."""
    return {"payload": {"core": {"memory_type": memory_type, "hrid": hrid, "user_id": "test_user"}}}


def test_hrid_generation_without_storage():
    """Test that HRID generation works without storage (backward compatibility)."""
    reset_counters()

    # Should generate fresh HRIDs starting from AAA000
    hrid1 = generate_hrid("memo")
    hrid2 = generate_hrid("memo")
    hrid3 = generate_hrid("memo_test")

    assert hrid1 == "MEMO_AAA000"
    assert hrid2 == "MEMO_AAA001"
    assert hrid3 == "MEMO_TEST_AAA000"


def test_hrid_generation_with_empty_storage():
    """Test HRID generation when storage has no existing memories."""
    reset_counters()
    storage = MockStorage([])

    hrid1 = generate_hrid("memo", storage)
    hrid2 = generate_hrid("memo", storage)

    assert hrid1 == "MEMO_AAA000"
    assert hrid2 == "MEMO_AAA001"


def test_hrid_generation_continues_from_existing():
    """Test that HRID generation continues from highest existing HRID in storage."""
    reset_counters()

    # Mock storage with existing memories
    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA002"),
        create_mock_memory("memo", "MEMO_AAA000"),
        create_mock_memory("memo", "MEMO_AAA001"),
        create_mock_memory("memo_test", "MEMO_TEST_AAA005"),
    ]
    storage = MockStorage(existing_memories)

    # Should continue from MEMO_AAA003 (after highest existing MEMO_AAA002)
    hrid1 = generate_hrid("memo", storage)
    hrid2 = generate_hrid("memo", storage)

    # Should continue from MEMO_TEST_AAA006 (after highest existing MEMO_TEST_AAA005)
    hrid3 = generate_hrid("memo_test", storage)

    assert hrid1 == "MEMO_AAA003"
    assert hrid2 == "MEMO_AAA004"
    assert hrid3 == "MEMO_TEST_AAA006"


def test_hrid_generation_handles_alpha_rollover():
    """Test HRID generation when existing memories are near AAA999."""
    reset_counters()

    # Mock storage with memories near the rollover point
    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA998"),
        create_mock_memory("memo", "MEMO_AAA999"),
    ]
    storage = MockStorage(existing_memories)

    # Should rollover to AAB000
    hrid1 = generate_hrid("memo", storage)
    hrid2 = generate_hrid("memo", storage)

    assert hrid1 == "MEMO_AAB000"
    assert hrid2 == "MEMO_AAB001"


def test_hrid_generation_skips_invalid_hrids():
    """Test that invalid HRIDs in storage are ignored."""
    reset_counters()

    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA001"),
        create_mock_memory("memo", "INVALID_HRID"),  # Should be ignored
        create_mock_memory("memo", "MEMO_BBB_WRONG"),  # Should be ignored
        create_mock_memory("memo", None),  # Should be ignored
        create_mock_memory("memo", "MEMO_AAA003"),
    ]
    storage = MockStorage(existing_memories)

    # Should continue from MEMO_AAA004 (ignoring invalid HRIDs)
    hrid = generate_hrid("memo", storage)
    assert hrid == "MEMO_AAA004"


def test_hrid_generation_filters_by_memory_type():
    """Test that HRID generation only considers same memory type."""
    reset_counters()

    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA005"),
        create_mock_memory(
            "memo_test", "MEMO_TEST_AAA010"
        ),  # Different type, should be ignored for memo
        create_mock_memory("other", "OTHER_AAA020"),  # Different type, should be ignored for memo
    ]
    storage = MockStorage(existing_memories)

    # Should continue from MEMO_AAA006 (only considering memo type)
    hrid = generate_hrid("memo", storage)
    assert hrid == "MEMO_AAA006"


def test_hrid_generation_handles_storage_errors():
    """Test that storage errors fallback to fresh counter."""
    reset_counters()

    # Mock storage that raises exceptions
    storage = MagicMock(spec=StorageQueryInterface)
    storage.search_points.side_effect = Exception("Storage error")

    # Should fallback to fresh counter despite storage error
    hrid = generate_hrid("memo", storage)
    assert hrid == "MEMO_AAA000"


def test_initialize_counter_from_storage_direct():
    """Test the _initialize_counter_from_storage function directly."""
    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA010"),
        create_mock_memory("memo", "MEMO_AAA012"),
    ]
    storage = MockStorage(existing_memories)

    # Should return (0, 12) representing next position after MEMO_AAA012
    alpha_idx, num = _initialize_counter_from_storage("memo", storage)
    assert alpha_idx == 0  # Still in AAA range
    assert num == 12  # Will be incremented to 13 by generate_hrid


def test_hrid_case_insensitive_memory_type():
    """Test that memory type matching is case insensitive."""
    reset_counters()

    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA005"),  # lowercase in storage
    ]
    storage = MockStorage(existing_memories)

    # Generate with uppercase - should still find existing memories
    hrid = generate_hrid("MEMO", storage)
    assert hrid == "MEMO_AAA006"


def test_hrid_generation_caches_counter():
    """Test that counter is cached after first storage query."""
    reset_counters()

    existing_memories = [
        create_mock_memory("memo", "MEMO_AAA005"),
    ]
    storage = MockStorage(existing_memories)

    # Mock the search_points method to track calls
    original_search = storage.search_points
    call_count = {"count": 0}

    def tracked_search(*args, **kwargs):
        call_count["count"] += 1
        return original_search(*args, **kwargs)

    storage.search_points = tracked_search

    # First call should query storage
    hrid1 = generate_hrid("memo", storage)
    assert hrid1 == "MEMO_AAA006"

    # Subsequent calls should use cached counter (not query storage again)
    hrid2 = generate_hrid("memo", storage)
    hrid3 = generate_hrid("memo", storage)

    assert hrid2 == "MEMO_AAA007"
    assert hrid3 == "MEMO_AAA008"

    # Storage should have been queried only once (for the first call)
    assert call_count["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
