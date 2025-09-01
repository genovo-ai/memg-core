"""Custom exception hierarchy for the memory system - minimal set."""

from typing import Any


class MemorySystemError(Exception):
    """Base exception for all memory system errors.

    Attributes:
        message: Error message.
        operation: Operation that caused the error.
        context: Additional context information.
        original_error: Original exception that was wrapped.
    """

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        self.message = message
        self.operation = operation
        self.context = context or {}
        self.original_error = original_error

        # Build detailed error message
        full_message = message
        if operation:
            full_message = f"[{operation}] {message}"
        if original_error:
            full_message += f" (caused by: {original_error})"

        super().__init__(full_message)


class ConfigurationError(MemorySystemError):
    """Configuration-related errors (env vars, validation)."""


class DatabaseError(MemorySystemError):
    """Database operation failures (Qdrant, Kuzu)."""


class ValidationError(MemorySystemError):
    """Data validation failures (schema, input format)."""


class ProcessingError(MemorySystemError):
    """Memory processing operation failures (catch-all for processing)."""


def wrap_exception(
    original_error: Exception, operation: str, context: dict[str, Any] | None = None
) -> MemorySystemError:
    """Wrap a generic exception in an appropriate MemorySystemError subclass.

    Args:
        original_error: Original exception to wrap.
        operation: Operation that caused the error.
        context: Additional context information.

    Returns:
        MemorySystemError: Wrapped exception with appropriate subclass.
    """
    error_message = str(original_error)

    # Map common exceptions to our hierarchy

    if isinstance(original_error, (FileNotFoundError, PermissionError)):
        return DatabaseError(
            f"Storage error: {error_message}",
            operation=operation,
            context=context,
            original_error=original_error,
        )

    if isinstance(original_error, ValueError):
        return ValidationError(
            f"Invalid value: {error_message}",
            operation=operation,
            context=context,
            original_error=original_error,
        )

    # Default to generic ProcessingError for unknown exceptions
    return ProcessingError(
        f"Unexpected error: {error_message}",
        operation=operation,
        context=context,
        original_error=original_error,
    )


def handle_with_context(operation: str):
    """Decorator for consistent error handling with context.

    Args:
        operation: Operation name for error context.

    Returns:
        callable: Decorated function with error handling.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except MemorySystemError:
                # Re-raise our own exceptions as-is
                raise
            except Exception as e:
                # Wrap unknown exceptions
                raise wrap_exception(e, operation, {"args": args, "kwargs": kwargs}) from e

        return wrapper

    return decorator
