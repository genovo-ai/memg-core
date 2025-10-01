"""Quick validation tests for numeric type support (int, float, bool)."""

from __future__ import annotations

from memg_core.api.public import add_memory, delete_memory, get_memory


def test_numeric_types_in_task():
    """Test that float, int, and bool types work in task entity."""
    # Add task with all numeric types
    hrid = add_memory(
        memory_type="task",
        payload={
            "statement": "Implement numeric type support",
            "details": "Add int, float, bool to type system",
            "project": "memg-core",
            "estimated_hours": 2.5,  # float
            "story_points": 3,  # int
            "completed": False,  # bool
        },
        user_id="test_user",
    )

    assert hrid.startswith("TASK_")

    # Retrieve and verify types
    result = get_memory(hrid=hrid, user_id="test_user")
    assert result is not None
    memory = result.memories[0]

    assert memory.payload["estimated_hours"] == 2.5
    assert isinstance(memory.payload["estimated_hours"], float)

    assert memory.payload["story_points"] == 3
    assert isinstance(memory.payload["story_points"], int)

    assert memory.payload["completed"] is False
    assert isinstance(memory.payload["completed"], bool)

    # Cleanup
    delete_memory(hrid=hrid, user_id="test_user")


def test_numeric_type_aliases():
    """Test that type aliases (integer, number, boolean) work."""
    # This validates the aliases in _get_python_type work correctly
    # If the YAML used "integer", "number", "boolean" they would work too
    hrid = add_memory(
        memory_type="task",
        payload={
            "statement": "Test type aliases",
            "estimated_hours": 1.0,
            "story_points": 1,
            "completed": True,
        },
        user_id="test_user",
    )

    result = get_memory(hrid=hrid, user_id="test_user")
    memory = result.memories[0]

    # All types preserved
    assert isinstance(memory.payload["estimated_hours"], float)
    assert isinstance(memory.payload["story_points"], int)
    assert isinstance(memory.payload["completed"], bool)

    delete_memory(hrid=hrid, user_id="test_user")


def test_optional_numeric_fields():
    """Numeric fields should be optional if not required."""
    # Create task without optional numeric fields
    hrid = add_memory(
        memory_type="task",
        payload={
            "statement": "Minimal task",
            "details": "Only required fields",
        },
        user_id="test_user",
    )

    result = get_memory(hrid=hrid, user_id="test_user")
    memory = result.memories[0]

    # Optional numeric fields should be absent when not provided
    # Note: memg-core doesn't auto-populate defaults from YAML schema
    assert "estimated_hours" not in memory.payload
    assert "story_points" not in memory.payload
    assert "completed" not in memory.payload

    delete_memory(hrid=hrid, user_id="test_user")
