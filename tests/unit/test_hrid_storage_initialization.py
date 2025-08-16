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
            if core.get("memory_type") == memory_type_filter:
                filtered.append(memory)

        return filtered[:limit]


def create_mock_memory(memory_type, hrid):
    """Helper to create mock memory with specific HRID."""
    return {"payload": {"core": {"memory_type": memory_type, "hrid": hrid, "user_id": "test_user"}}}


def test_hrid_generation_without_storage():
    """Test that HRID generation works without storage (backward compatibility)."""
    reset_counters()

    # Should generate fresh HRIDs starting from AAA000
    hrid1 = generate_hrid("note")
    hrid2 = generate_hrid("note")
    hrid3 = generate_hrid("task")

    assert hrid1 == "NOTE_AAA000"
    assert hrid2 == "NOTE_AAA001"
    assert hrid3 == "TASK_AAA000"


def test_hrid_generation_with_empty_storage():
    """Test HRID generation when storage has no existing memories."""
    reset_counters()
    storage = MockStorage([])

    hrid1 = generate_hrid("note", storage)
    hrid2 = generate_hrid("note", storage)

    assert hrid1 == "NOTE_AAA000"
    assert hrid2 == "NOTE_AAA001"


def test_hrid_generation_continues_from_existing():
    """Test that HRID generation continues from highest existing HRID in storage."""
    reset_counters()

    # Mock storage with existing memories
    existing_memories = [
        create_mock_memory("note", "NOTE_AAA002"),
        create_mock_memory("note", "NOTE_AAA000"),
        create_mock_memory("note", "NOTE_AAA001"),
        create_mock_memory("task", "TASK_AAA005"),
    ]
    storage = MockStorage(existing_memories)

    # Should continue from NOTE_AAA003 (after highest existing NOTE_AAA002)
    hrid1 = generate_hrid("note", storage)
    hrid2 = generate_hrid("note", storage)

    # Should continue from TASK_AAA006 (after highest existing TASK_AAA005)
    hrid3 = generate_hrid("task", storage)

    assert hrid1 == "NOTE_AAA003"
    assert hrid2 == "NOTE_AAA004"
    assert hrid3 == "TASK_AAA006"


def test_hrid_generation_handles_alpha_rollover():
    """Test HRID generation when existing memories are near AAA999."""
    reset_counters()

    # Mock storage with memories near the rollover point
    existing_memories = [
        create_mock_memory("note", "NOTE_AAA998"),
        create_mock_memory("note", "NOTE_AAA999"),
    ]
    storage = MockStorage(existing_memories)

    # Should rollover to AAB000
    hrid1 = generate_hrid("note", storage)
    hrid2 = generate_hrid("note", storage)

    assert hrid1 == "NOTE_AAB000"
    assert hrid2 == "NOTE_AAB001"


def test_hrid_generation_skips_invalid_hrids():
    """Test that invalid HRIDs in storage are ignored."""
    reset_counters()

    existing_memories = [
        create_mock_memory("note", "NOTE_AAA001"),
        create_mock_memory("note", "INVALID_HRID"),  # Should be ignored
        create_mock_memory("note", "NOTE_BBB_WRONG"),  # Should be ignored
        create_mock_memory("note", None),  # Should be ignored
        create_mock_memory("note", "NOTE_AAA003"),
    ]
    storage = MockStorage(existing_memories)

    # Should continue from NOTE_AAA004 (ignoring invalid HRIDs)
    hrid = generate_hrid("note", storage)
    assert hrid == "NOTE_AAA004"


def test_hrid_generation_filters_by_memory_type():
    """Test that HRID generation only considers same memory type."""
    reset_counters()

    existing_memories = [
        create_mock_memory("note", "NOTE_AAA005"),
        create_mock_memory("task", "TASK_AAA010"),  # Different type, should be ignored for notes
        create_mock_memory("memo", "MEMO_AAA020"),  # Different type, should be ignored for notes
    ]
    storage = MockStorage(existing_memories)

    # Should continue from NOTE_AAA006 (only considering note type)
    hrid = generate_hrid("note", storage)
    assert hrid == "NOTE_AAA006"


def test_hrid_generation_handles_storage_errors():
    """Test that storage errors fallback to fresh counter."""
    reset_counters()

    # Mock storage that raises exceptions
    storage = MagicMock(spec=StorageQueryInterface)
    storage.search_points.side_effect = Exception("Storage error")

    # Should fallback to fresh counter despite storage error
    hrid = generate_hrid("note", storage)
    assert hrid == "NOTE_AAA000"


def test_initialize_counter_from_storage_direct():
    """Test the _initialize_counter_from_storage function directly."""
    existing_memories = [
        create_mock_memory("note", "NOTE_AAA010"),
        create_mock_memory("note", "NOTE_AAA012"),
    ]
    storage = MockStorage(existing_memories)

    # Should return (0, 12) representing next position after NOTE_AAA012
    alpha_idx, num = _initialize_counter_from_storage("note", storage)
    assert alpha_idx == 0  # Still in AAA range
    assert num == 12  # Will be incremented to 13 by generate_hrid


def test_hrid_case_insensitive_memory_type():
    """Test that memory type matching is case insensitive."""
    reset_counters()

    existing_memories = [
        create_mock_memory("note", "NOTE_AAA005"),  # lowercase in storage
    ]
    storage = MockStorage(existing_memories)

    # Generate with uppercase - should still find existing memories
    hrid = generate_hrid("NOTE", storage)
    assert hrid == "NOTE_AAA006"


def test_hrid_generation_caches_counter():
    """Test that counter is cached after first storage query."""
    reset_counters()

    existing_memories = [
        create_mock_memory("note", "NOTE_AAA005"),
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
    hrid1 = generate_hrid("note", storage)
    assert hrid1 == "NOTE_AAA006"

    # Subsequent calls should use cached counter (not query storage again)
    hrid2 = generate_hrid("note", storage)
    hrid3 = generate_hrid("note", storage)

    assert hrid2 == "NOTE_AAA007"
    assert hrid3 == "NOTE_AAA008"

    # Storage should have been queried only once (for the first call)
    assert call_count["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
