"""Unit tests for exception handling and logging."""

import pytest

pytestmark = pytest.mark.unit

from unittest.mock import patch

import pytest

from memg_core.core.exceptions import (
    DatabaseError,
    ValidationError,
    handle_with_context,
    wrap_exception,
)
from memg_core.core.logging import (
    MemorySystemLogger,
    log_error,
    log_operation,
)


def test_wrap_exception_maps_valueerror_to_validationerror():
    """Test that wrap_exception maps ValueError to ValidationError."""
    original_error = ValueError("Invalid value")
    wrapped_error = wrap_exception(original_error, "test_operation")

    assert isinstance(wrapped_error, ValidationError)
    assert "Invalid value" in str(wrapped_error)
    assert wrapped_error.operation == "test_operation"
    assert wrapped_error.original_error is original_error


def test_wrap_exception_maps_connection_error_to_networkerror():
    """Test that wrap_exception maps FileNotFoundError to DatabaseError."""
    original_error = FileNotFoundError("Database file not found")
    wrapped_error = wrap_exception(original_error, "test_operation")

    assert isinstance(wrapped_error, DatabaseError)
    assert "Database file not found" in str(wrapped_error)
    assert wrapped_error.operation == "test_operation"
    assert wrapped_error.original_error is original_error


def test_wrap_exception_maps_file_errors_to_databaseerror():
    """Test that wrap_exception maps file errors to DatabaseError."""
    # Test FileNotFoundError
    original_error = FileNotFoundError("File not found")
    wrapped_error = wrap_exception(original_error, "test_operation")

    assert isinstance(wrapped_error, DatabaseError)
    assert "File not found" in str(wrapped_error)

    # Test PermissionError
    original_error = PermissionError("Permission denied")
    wrapped_error = wrap_exception(original_error, "test_operation")

    assert isinstance(wrapped_error, DatabaseError)
    assert "Permission denied" in str(wrapped_error)


def test_wrap_exception_with_context():
    """Test that wrap_exception includes context."""
    original_error = ValueError("Invalid value")
    context = {"param": "test", "value": 123}
    wrapped_error = wrap_exception(original_error, "test_operation", context)

    assert wrapped_error.context == context


def test_handle_with_context_preserves_operation():
    """Test that handle_with_context decorator preserves operation name."""

    @handle_with_context("test_operation")
    def function_that_raises():
        raise ValueError("Test error")

    with pytest.raises(ValidationError) as exc_info:
        function_that_raises()

    assert exc_info.value.operation == "test_operation"
    assert "Test error" in str(exc_info.value)


def test_handle_with_context_passes_through_memory_system_errors():
    """Test that handle_with_context passes through MemorySystemErrors."""

    @handle_with_context("test_operation")
    def function_that_raises_memory_error():
        raise ValidationError("Already wrapped", operation="original_operation")

    with pytest.raises(ValidationError) as exc_info:
        function_that_raises_memory_error()

    assert exc_info.value.operation == "original_operation"
    assert "Already wrapped" in str(exc_info.value)


@patch("logging.Logger")
def test_memory_system_logger_setup(mock_logger):
    """Test that MemorySystemLogger setup works correctly."""
    # Reset the logger state for testing
    MemorySystemLogger._configured = False
    MemorySystemLogger._loggers = {}

    with patch("logging.getLogger") as mock_get_logger:
        mock_get_logger.return_value = mock_logger
        _ = MemorySystemLogger.setup_logging(level="INFO")

        # Check that the root logger was created
        mock_get_logger.assert_called_with("memg_core")

        # Check that handlers were set up
        assert mock_logger.addHandler.called
        assert mock_logger.setLevel.called


@patch("logging.Logger")
def test_log_operation_formats_context(mock_logger):
    """Test that log_operation formats context correctly."""
    # Reset the logger state for testing
    MemorySystemLogger._configured = False
    MemorySystemLogger._loggers = {}

    with patch("memg_core.core.logging.MemorySystemLogger.get_logger") as mock_get_logger:
        mock_get_logger.return_value = mock_logger

        # Call log_operation with context
        log_operation("test_component", "test_operation", user_id="test-user", count=123)

        # Check that the message was formatted correctly
        mock_logger.info.assert_called_once()
        message = mock_logger.info.call_args[0][0]

        assert "[test_operation]" in message
        assert "user_id=test-user" in message
        assert "count=123" in message


@patch("logging.Logger")
def test_log_error_includes_exception_info(mock_logger):
    """Test that log_error includes exception info."""
    # Reset the logger state for testing
    MemorySystemLogger._configured = False
    MemorySystemLogger._loggers = {}

    with patch("memg_core.core.logging.MemorySystemLogger.get_logger") as mock_get_logger:
        mock_get_logger.return_value = mock_logger

        # Call log_error with an exception
        error = ValueError("Test error")
        log_error("test_component", "test_operation", error, user_id="test-user")

        # Check that the error was logged correctly
        mock_logger.error.assert_called_once()
        message = mock_logger.error.call_args[0][0]
        exc_info = mock_logger.error.call_args[1].get("exc_info")

        assert "❌" in message
        assert "[test_operation]" in message
        assert "ValueError" in message
        assert "Test error" in message
        assert "user_id=test-user" in message
        assert exc_info is True  # Exception traceback should be included
