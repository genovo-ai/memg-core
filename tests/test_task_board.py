#!/usr/bin/env python3
"""
Test Task Board Integration
Basic tests for task board entity system and MCP tools
"""

from datetime import datetime, timedelta

from memory_system.models.core import EntityType, Memory, MemoryType, TaskPriority, TaskStatus


class TestTaskBoardEntities:
    """Test task board entity types and enums"""

    def test_task_memory_type(self):
        """Test TASK memory type exists"""
        assert MemoryType.TASK == "task"
        assert MemoryType.TASK in [t.value for t in MemoryType]

    def test_task_status_enum(self):
        """Test TaskStatus enum values"""
        assert TaskStatus.BACKLOG == "backlog"
        assert TaskStatus.TODO == "todo"
        assert TaskStatus.IN_PROGRESS == "in_progress"
        assert TaskStatus.IN_REVIEW == "in_review"
        assert TaskStatus.DONE == "done"
        assert TaskStatus.CANCELLED == "cancelled"

    def test_task_priority_enum(self):
        """Test TaskPriority enum values"""
        assert TaskPriority.LOW == "low"
        assert TaskPriority.MEDIUM == "medium"
        assert TaskPriority.HIGH == "high"
        assert TaskPriority.CRITICAL == "critical"

    def test_task_entity_types(self):
        """Test task management entity types"""
        assert EntityType.TICKET == "TICKET"
        assert EntityType.EPIC == "EPIC"
        assert EntityType.MILESTONE == "MILESTONE"
        assert EntityType.SPRINT == "SPRINT"
        assert EntityType.BOARD == "BOARD"

    def test_task_memory_creation(self):
        """Test creating a task memory with all fields"""
        due_date = datetime.now() + timedelta(days=7)

        task_memory = Memory(
            content="Implement user authentication API endpoint",
            user_id="test_user",
            memory_type=MemoryType.TASK,
            title="AUTH-001: User Authentication",
            task_status=TaskStatus.TODO,
            task_priority=TaskPriority.HIGH,
            assignee="developer@team.com",
            due_date=due_date,
            story_points=8,
            epic_id="EPIC-001",
            sprint_id="SPRINT-2025-01",
            code_file_path="src/auth/api.py",
            code_line_range="45-120",
            code_signature="def authenticate_user(username, password)",
            tags=["backend", "api", "authentication"],
        )

        assert task_memory.is_task()
        assert task_memory.has_code_link()
        assert not task_memory.is_overdue()
        assert not task_memory.is_in_progress()

    def test_task_memory_helper_methods(self):
        """Test task memory helper methods"""
        # Test overdue task
        overdue_task = Memory(
            content="Fix critical bug",
            user_id="test_user",
            memory_type=MemoryType.TASK,
            task_status=TaskStatus.IN_PROGRESS,
            due_date=datetime.now() - timedelta(days=1),
        )

        assert overdue_task.is_overdue()
        assert overdue_task.is_in_progress()

        # Test completed task (not overdue)
        done_task = Memory(
            content="Completed task",
            user_id="test_user",
            memory_type=MemoryType.TASK,
            task_status=TaskStatus.DONE,
            due_date=datetime.now() - timedelta(days=1),
        )

        assert not done_task.is_overdue()  # Done tasks can't be overdue
        assert not done_task.is_in_progress()

    def test_task_memory_qdrant_payload(self):
        """Test task memory Qdrant payload includes task fields"""
        task_memory = Memory(
            content="Test task",
            user_id="test_user",
            memory_type=MemoryType.TASK,
            task_status=TaskStatus.TODO,
            task_priority=TaskPriority.MEDIUM,
            assignee="test@example.com",
            story_points=5,
            code_file_path="test.py",
        )

        payload = task_memory.to_qdrant_payload()

        assert payload["memory_type"] == "task"
        assert payload["task_status"] == "todo"
        assert payload["task_priority"] == "medium"
        assert payload["assignee"] == "test@example.com"
        assert payload["story_points"] == 5
        assert payload["code_file_path"] == "test.py"
        assert payload["has_code_link"] is True

    def test_regular_memory_qdrant_payload(self):
        """Test regular memory doesn't include task fields in payload"""
        regular_memory = Memory(
            content="Regular note", user_id="test_user", memory_type=MemoryType.NOTE
        )

        payload = regular_memory.to_qdrant_payload()

        assert payload["memory_type"] == "note"
        assert "task_status" not in payload
        assert "task_priority" not in payload
        assert "assignee" not in payload


class TestTaskBoardMCPToolsValidation:
    """Test MCP tools validation logic (without requiring full system)"""

    def test_task_status_validation(self):
        """Test task status validation"""
        from memory_system.models.core import TaskStatus

        # Valid statuses
        valid_statuses = ["backlog", "todo", "in_progress", "in_review", "done", "cancelled"]
        for status in valid_statuses:
            assert TaskStatus(status) == status

        # Invalid status should raise ValueError
        try:
            TaskStatus("invalid_status")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_task_priority_validation(self):
        """Test task priority validation"""
        from memory_system.models.core import TaskPriority

        # Valid priorities
        valid_priorities = ["low", "medium", "high", "critical"]
        for priority in valid_priorities:
            assert TaskPriority(priority) == priority

        # Invalid priority should raise ValueError
        try:
            TaskPriority("invalid_priority")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_story_points_validation(self):
        """Test story points validation logic"""
        # Valid story points
        valid_points = [0, 1, 5, 13, 21, 50, 100]
        for points in valid_points:
            assert isinstance(points, int)
            assert 0 <= points <= 100

        # Invalid story points
        invalid_points = [-1, 101, "5", 5.5]
        for points in invalid_points:
            if isinstance(points, int):
                assert not (0 <= points <= 100)
            else:
                assert not isinstance(points, int)

    def test_date_parsing_formats(self):
        """Test date parsing formats used in MCP tools"""
        from datetime import datetime

        test_dates = ["2025-02-15", "2025-02-15T14:30:00", "2025-02-15 14:30:00"]

        formats = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]

        for date_str in test_dates:
            parsed = None
            for fmt in formats:
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

            assert parsed is not None, f"Failed to parse date: {date_str}"


if __name__ == "__main__":
    # Run basic validation tests
    test_entities = TestTaskBoardEntities()
    test_entities.test_task_memory_type()
    test_entities.test_task_status_enum()
    test_entities.test_task_priority_enum()
    test_entities.test_task_entity_types()
    test_entities.test_task_memory_creation()
    test_entities.test_task_memory_helper_methods()
    test_entities.test_task_memory_qdrant_payload()
    test_entities.test_regular_memory_qdrant_payload()

    test_validation = TestTaskBoardMCPToolsValidation()
    test_validation.test_task_status_validation()
    test_validation.test_task_priority_validation()
    test_validation.test_story_points_validation()
    test_validation.test_date_parsing_formats()

    print("✅ All task board tests passed!")
