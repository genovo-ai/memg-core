"""Unit tests for core models and validators."""

import pytest
from datetime import UTC, datetime, timedelta
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from memg_core.core.models import Memory


def test_memory_type_required():
    """Test that memory type is required."""
    # Empty memory_type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", memory_type="")

    assert "memory_type" in str(exc_info.value)

    # Whitespace-only memory_type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", memory_type="   ")

    assert "memory_type" in str(exc_info.value)

    # Valid memory_type should not raise
    memory = Memory(user_id="test-user", memory_type="note")
    assert memory.memory_type == "note"


def test_memory_to_qdrant_payload_shapes_by_type():
    """Test that Memory.to_qdrant_payload() returns correct nested structure."""
    # Test NOTE type
    note_memory = Memory(
        user_id="test-user",
        memory_type="note",
        payload={
            "content": "Test content",
            "title": "Test Title",
            "source": "user"
        },
        tags=["test", "memory"],
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    note_payload = note_memory.to_qdrant_payload()

    assert "core" in note_payload
    assert "entity" in note_payload
    assert note_payload["core"]["memory_type"] == "note"
    assert note_payload["core"]["user_id"] == "test-user"
    assert note_payload["core"]["tags"] == ["test", "memory"]
    assert note_payload["core"]["created_at"] == "2023-01-01T00:00:00+00:00"
    assert note_payload["entity"]["content"] == "Test content"
    assert note_payload["entity"]["title"] == "Test Title"

    # Test TASK type with task fields
    due_date = datetime.now(UTC) + timedelta(days=1)
    task_memory = Memory(
        user_id="test-user",
        memory_type="task",
        payload={
            "summary": "Fix bug",
            "content": "Detailed description",
            "task_status": "todo",
            "task_priority": "high",
            "assignee": "test-user",
            "due_date": due_date,
        },
        tags=["task"],
    )
    task_payload = task_memory.to_qdrant_payload()

    assert task_payload["core"]["memory_type"] == "task"
    assert task_payload["entity"]["summary"] == "Fix bug"
    assert task_payload["entity"]["task_status"] == "todo"
    assert task_payload["entity"]["task_priority"] == "high"
    assert task_payload["entity"]["assignee"] == "test-user"


def test_memory_to_kuzu_node_core_fields_only():
    """Test that Memory.to_kuzu_node() stores only core metadata."""
    # Create a memory with detailed payload
    memory = Memory(
        user_id="test-user",
        memory_type="task",
        payload={
            "summary": "Test task",
            "content": "x" * 1000,  # Long content should NOT be in Kuzu
            "title": "Test Title",
            "task_status": "in_progress",
            "assignee": "developer"
        },
        tags=["test", "kuzu"],
    )

    kuzu_node = memory.to_kuzu_node()

    # Core fields should be present
    assert kuzu_node["user_id"] == "test-user"
    assert kuzu_node["memory_type"] == "task"
    assert kuzu_node["tags"] == "test,kuzu"

    # Title should be truncated and present
    assert kuzu_node["title"] == "Test Title"

    # Task-specific fields should be present (for relationship purposes)
    assert kuzu_node["task_status"] == "in_progress"
    assert kuzu_node["assignee"] == "developer"

    # NO detailed content should be stored in Kuzu
    assert "content" not in kuzu_node
    assert "summary" not in kuzu_node

    # Empty fields should be empty strings, not None
    assert kuzu_node["supersedes"] == ""
    assert kuzu_node["superseded_by"] == ""


def test_task_due_date_handling():
    """Test that task due date handling works correctly with UTC dates."""
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    # Create tasks with different due dates
    overdue_task = Memory(
        user_id="test-user",
        memory_type="task",
        payload={
            "summary": "Overdue task",
            "due_date": yesterday,
        },
    )

    future_task = Memory(
        user_id="test-user",
        memory_type="task",
        payload={
            "summary": "Future task",
            "due_date": tomorrow,
        },
    )

    no_due_date_task = Memory(
        user_id="test-user",
        memory_type="task",
        payload={
            "summary": "No due date task",
        },
    )

    # Test serialization to Qdrant payload
    overdue_payload = overdue_task.to_qdrant_payload()
    future_payload = future_task.to_qdrant_payload()
    no_due_date_payload = no_due_date_task.to_qdrant_payload()

    assert overdue_payload["entity"]["due_date"] == yesterday
    assert future_payload["entity"]["due_date"] == tomorrow
    assert "due_date" not in no_due_date_payload["entity"]
