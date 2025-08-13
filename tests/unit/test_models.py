"""Unit tests for core models and validators."""

import pytest
from datetime import UTC, datetime, timedelta
from pydantic import ValidationError

pytestmark = pytest.mark.unit

from memg_core.core.models import Memory, MemoryType, TaskStatus, TaskPriority


def test_memory_content_required():
    """Test that memory content is required."""
    # Empty content should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", content="")

    assert "content" in str(exc_info.value)

    # Whitespace-only content should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", content="   ")

    assert "content" in str(exc_info.value)

    # Valid content should not raise
    memory = Memory(user_id="test-user", content="Valid content")
    assert memory.content == "Valid content"


def test_memory_to_qdrant_payload_shapes_by_type():
    """Test that Memory.to_qdrant_payload() returns correct shapes by memory type."""
    # Create a base memory
    base_memory = Memory(
        user_id="test-user",
        content="Test content",
        title="Test Title",
        tags=["test", "memory"],
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )

    # Test NOTE type
    note_memory = base_memory.model_copy(update={"memory_type": MemoryType.NOTE})
    note_payload = note_memory.to_qdrant_payload()

    assert note_payload["memory_type"] == "note"
    assert note_payload["user_id"] == "test-user"
    assert note_payload["content"] == "Test content"
    assert note_payload["title"] == "Test Title"
    assert note_payload["tags"] == ["test", "memory"]
    assert note_payload["created_at"] == "2023-01-01T00:00:00+00:00"
    assert "task_status" not in note_payload

    # Test DOCUMENT type with summary
    doc_memory = base_memory.model_copy(
        update={
            "memory_type": MemoryType.DOCUMENT,
            "summary": "Test summary"
        }
    )
    doc_payload = doc_memory.to_qdrant_payload()

    assert doc_payload["memory_type"] == "document"
    assert doc_payload["summary"] == "Test summary"
    assert "task_status" not in doc_payload

    # Test TASK type with task fields
    due_date = datetime.now(UTC) + timedelta(days=1)
    task_memory = base_memory.model_copy(
        update={
            "memory_type": MemoryType.TASK,
            "task_status": TaskStatus.TODO,
            "task_priority": TaskPriority.HIGH,
            "assignee": "test-user",
            "due_date": due_date,
        }
    )
    task_payload = task_memory.to_qdrant_payload()

    assert task_payload["memory_type"] == "task"
    assert task_payload["task_status"] == "todo"
    assert task_payload["task_priority"] == "high"
    assert task_payload["assignee"] == "test-user"
    assert task_payload["due_date"] == due_date.isoformat()


def test_memory_to_kuzu_node_truncates_content():
    """Test that Memory.to_kuzu_node() truncates content to 500 chars."""
    # Create a memory with long content
    long_content = "x" * 1000
    memory = Memory(
        user_id="test-user",
        content=long_content,
    )

    kuzu_node = memory.to_kuzu_node()

    # Content should be truncated to 500 chars
    assert len(kuzu_node["content"]) == 500
    assert kuzu_node["content"] == "x" * 500

    # Other fields should be present
    assert kuzu_node["user_id"] == "test-user"
    assert kuzu_node["memory_type"] == "note"

    # Empty fields should be empty strings, not None
    assert kuzu_node["summary"] == ""
    assert kuzu_node["title"] == ""
    assert kuzu_node["supersedes"] == ""
    assert kuzu_node["superseded_by"] == ""


def test_task_overdue_logic_utc():
    """Test that task due date handling works correctly with UTC dates."""
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    # Create tasks with different due dates
    overdue_task = Memory(
        user_id="test-user",
        content="Overdue task",
        memory_type=MemoryType.TASK,
        due_date=yesterday,
    )

    future_task = Memory(
        user_id="test-user",
        content="Future task",
        memory_type=MemoryType.TASK,
        due_date=tomorrow,
    )

    no_due_date_task = Memory(
        user_id="test-user",
        content="No due date task",
        memory_type=MemoryType.TASK,
    )

    # Test serialization to Qdrant payload
    overdue_payload = overdue_task.to_qdrant_payload()
    future_payload = future_task.to_qdrant_payload()
    no_due_date_payload = no_due_date_task.to_qdrant_payload()

    assert overdue_payload["due_date"] == yesterday.isoformat()
    assert future_payload["due_date"] == tomorrow.isoformat()
    assert no_due_date_payload["due_date"] is None
