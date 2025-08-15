"""Unit tests for core models and validators."""

import pytest
from datetime import UTC, datetime, timedelta
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from memg_core.core.models import Memory


def test_memory_type_required():
    """Test that memory type is required."""
    # Empty type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", type="", statement="test")

    assert "type" in str(exc_info.value)

    # Whitespace-only type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", type="   ", statement="test")

    assert "type" in str(exc_info.value)

    # Valid type should not raise
    memory = Memory(user_id="test-user", type="note", statement="test")
    assert memory.type == "note"


def test_memory_to_qdrant_payload_shapes_by_type():
    """Test that Memory.to_qdrant_payload() returns correct nested structure."""
    # Test NOTE type
    note_memory = Memory(
        user_id="test-user",
        type="note",
        statement="Test content",
        payload={
            "details": "This is the detail for the test note.",
        },
        tags=["test", "memory"],
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    note_payload = note_memory.to_qdrant_payload()

    assert "core" in note_payload
    assert "entity" in note_payload
    assert note_payload["core"]["type"] == "note"
    assert note_payload["core"]["user_id"] == "test-user"
    assert note_payload["core"]["tags"] == ["test", "memory"]
    assert note_payload["core"]["created_at"] == "2023-01-01T00:00:00+00:00"
    assert note_payload["entity"]["statement"] == "Test content"
    assert note_payload["entity"]["details"] == "This is the detail for the test note."

    # Test TASK type with task fields
    due_date = datetime.now(UTC) + timedelta(days=1)
    task_memory = Memory(
        user_id="test-user",
        type="task",
        statement="Fix bug",
        payload={
            "details": "Detailed description",
            "status": "todo",
            "priority": "high",
            "assignee": "test-user",
            "due_date": due_date,
        },
        tags=["task"],
    )
    task_payload = task_memory.to_qdrant_payload()

    assert task_payload["core"]["type"] == "task"
    assert task_payload["entity"]["statement"] == "Fix bug"
    assert task_payload["entity"]["status"] == "todo"
    assert task_payload["entity"]["priority"] == "high"
    assert task_payload["entity"]["assignee"] == "test-user"


def test_memory_to_kuzu_node_core_fields_only():
    """Test that Memory.to_kuzu_node() stores only core metadata."""
    # Create a memory with detailed payload
    memory = Memory(
        user_id="test-user",
        type="task",
        statement="Test task",
        payload={
            "details": "x" * 1000,  # Long content should NOT be in Kuzu
            "status": "in_progress",
            "assignee": "developer"
        },
        tags=["test", "kuzu"],
    )

    kuzu_node = memory.to_kuzu_node()

    # Core fields should be present
    assert kuzu_node["user_id"] == "test-user"
    assert kuzu_node["type"] == "task"
    assert kuzu_node["tags"] == "test,kuzu"

    # Statement should be truncated and present
    assert kuzu_node["statement"] == "Test task"

    # Task-specific fields should NOT be present
    assert "status" not in kuzu_node
    assert "assignee" not in kuzu_node
    assert "details" not in kuzu_node


def test_task_due_date_handling():
    """Test that task due date handling works correctly with UTC dates."""
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    # Create tasks with different due dates
    overdue_task = Memory(
        user_id="test-user",
        type="task",
        statement="Overdue task",
        payload={
            "due_date": yesterday,
        },
    )

    future_task = Memory(
        user_id="test-user",
        type="task",
        statement="Future task",
        payload={
            "due_date": tomorrow,
        },
    )

    no_due_date_task = Memory(
        user_id="test-user",
        type="task",
        statement="No due date task",
        payload={},
    )

    # Test serialization to Qdrant payload
    overdue_payload = overdue_task.to_qdrant_payload()
    future_payload = future_task.to_qdrant_payload()
    no_due_date_payload = no_due_date_task.to_qdrant_payload()

    assert overdue_payload["entity"]["due_date"] == yesterday
    assert future_payload["entity"]["due_date"] == tomorrow
    assert "due_date" not in no_due_date_payload["entity"]
