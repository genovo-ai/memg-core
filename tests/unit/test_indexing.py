"""Unit tests for indexing policy."""

import pytest

pytestmark = pytest.mark.unit

from memg_core.core.indexing import build_index_text
from memg_core.core.models import Memory, MemoryType


def test_indexing_note_uses_content():
    """Test that indexing a note uses its content."""
    memory = Memory(
        user_id="test-user",
        content="This is a test note",
        memory_type=MemoryType.NOTE,
        summary="This summary should be ignored for notes",
    )

    index_text = build_index_text(memory)

    assert index_text == "This is a test note"
    assert index_text != memory.summary  # Summary should be ignored


def test_indexing_document_prefers_summary_over_content():
    """Test that indexing a document prefers summary over content."""
    # Document with summary
    memory_with_summary = Memory(
        user_id="test-user",
        content="This is a long document content that should be ignored if summary exists",
        memory_type=MemoryType.DOCUMENT,
        summary="This is the document summary",
    )

    index_text = build_index_text(memory_with_summary)

    assert index_text == "This is the document summary"
    assert index_text != memory_with_summary.content

    # Document without summary should fall back to content
    memory_without_summary = Memory(
        user_id="test-user",
        content="This is document content",
        memory_type=MemoryType.DOCUMENT,
        summary=None,
    )

    index_text = build_index_text(memory_without_summary)

    assert index_text == "This is document content"

    # Document with empty summary should fall back to content
    memory_empty_summary = Memory(
        user_id="test-user",
        content="This is document content",
        memory_type=MemoryType.DOCUMENT,
        summary="   ",  # Just whitespace
    )

    index_text = build_index_text(memory_empty_summary)

    assert index_text == "This is document content"


def test_indexing_task_title_safe_join():
    """Test that indexing a task joins title and content safely."""
    # Task with title
    memory_with_title = Memory(
        user_id="test-user",
        content="Implement feature X",
        memory_type=MemoryType.TASK,
        title="MEMG-123",
    )

    index_text = build_index_text(memory_with_title)

    assert index_text == "MEMG-123. Implement feature X"

    # Task without title
    memory_without_title = Memory(
        user_id="test-user",
        content="Implement feature X",
        memory_type=MemoryType.TASK,
        title=None,
    )

    index_text = build_index_text(memory_without_title)

    assert index_text == "Implement feature X"

    # Task with empty title
    memory_empty_title = Memory(
        user_id="test-user",
        content="Implement feature X",
        memory_type=MemoryType.TASK,
        title="   ",  # Just whitespace
    )

    index_text = build_index_text(memory_empty_title)

    assert index_text == "Implement feature X"


def test_unknown_memory_type_falls_back_to_content():
    """Test that unknown memory types fall back to using content."""
    # Create a memory with an unknown type (bypassing enum validation)
    memory = Memory(
        user_id="test-user",
        content="This is content",
        summary="This is summary",
        title="This is title",
    )
    # Force an unknown type (this is a hack for testing)
    memory.memory_type = "unknown_type"  # type: ignore

    index_text = build_index_text(memory)

    assert index_text == "This is content"
