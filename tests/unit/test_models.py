"""Unit tests for core models and validators."""

from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
import pytest

pytestmark = pytest.mark.unit

from memg_core.core.models import Memory


def test_memory_type_required():
    """Test that memory type is required."""
    # Empty type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", memory_type="", payload={"statement": "test"})

    assert "memory_type" in str(exc_info.value)

    # Whitespace-only type should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        Memory(user_id="test-user", memory_type="   ", payload={"statement": "test"})

    assert "type" in str(exc_info.value)

    # Valid type should not raise
    memory = Memory(user_id="test-user", memory_type="memo", payload={"statement": "test"})
    assert memory.memory_type == "memo"


def test_memory_to_qdrant_payload_shapes_by_type():
    """Test that Memory.to_qdrant_payload() returns correct nested structure."""
    # Test MEMO type
    memo_memory = Memory(
        user_id="test-user",
        memory_type="memo",
        payload={
            "statement": "Test memo content",
        },
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    memo_payload = memo_memory.to_qdrant_payload()

    assert "core" in memo_payload
    assert "entity" in memo_payload
    assert memo_payload["core"]["memory_type"] == "memo"
    assert memo_payload["core"]["user_id"] == "test-user"
    # No hardcoded tags field - removed as part of audit
    assert memo_payload["core"]["created_at"] == "2023-01-01T00:00:00+00:00"
    assert memo_payload["entity"]["statement"] == "Test memo content"

    # Test MEMO_TEST type with all fields
    due_date = datetime.now(UTC) + timedelta(days=1)
    memo_test_memory = Memory(
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Fix bug",
            "details": "Detailed description",
            "status": "todo",
            "priority": "high",
            "assignee": "test-user",
            "due_date": due_date,
        },
        tags=["test"],
    )
    memo_test_payload = memo_test_memory.to_qdrant_payload()

    assert memo_test_payload["core"]["memory_type"] == "memo_test"
    assert memo_test_payload["entity"]["statement"] == "Fix bug"
    assert memo_test_payload["entity"]["status"] == "todo"
    assert memo_test_payload["entity"]["priority"] == "high"
    assert memo_test_payload["entity"]["assignee"] == "test-user"


def test_memory_to_kuzu_node_core_fields_only():
    """Test that Memory.to_kuzu_node() stores only core metadata."""
    # Create a memory with detailed payload
    memory = Memory(
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Test memo_test",
            "details": "x" * 1000,  # Long content should NOT be in Kuzu
            "status": "in_progress",
            "assignee": "developer",
        },
    )

    kuzu_node = memory.to_kuzu_node()

    # Core fields should be present
    assert kuzu_node["user_id"] == "test-user"
    assert kuzu_node["memory_type"] == "memo_test"
    # No hardcoded tags field - removed as part of audit

    # YAML-defined payload fields should NOT be in Kuzu (only core fields stored)
    assert "statement" not in kuzu_node  # Statement is in payload, not core
    assert "status" not in kuzu_node
    assert "assignee" not in kuzu_node
    assert "details" not in kuzu_node


def test_memo_test_due_date_handling():
    """Test that memo_test due date handling works correctly with UTC dates."""
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    tomorrow = now + timedelta(days=1)

    # Create memo_test instances with different due dates
    overdue_memo = Memory(
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Overdue memo_test",
            "due_date": yesterday,
        },
    )

    future_memo = Memory(
        user_id="test-user",
        memory_type="memo_test",
        payload={
            "statement": "Future memo_test",
            "due_date": tomorrow,
        },
    )

    no_due_date_memo = Memory(
        user_id="test-user",
        memory_type="memo_test",
        payload={"statement": "No due date memo_test"},
    )

    # Test serialization to Qdrant payload
    overdue_payload = overdue_memo.to_qdrant_payload()
    future_payload = future_memo.to_qdrant_payload()
    no_due_date_payload = no_due_date_memo.to_qdrant_payload()

    assert overdue_payload["entity"]["due_date"] == yesterday
    assert future_payload["entity"]["due_date"] == tomorrow
    assert "due_date" not in no_due_date_payload["entity"]
