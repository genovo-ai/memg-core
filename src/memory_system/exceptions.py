"""
Custom exception hierarchy for the memory system.

This module defines specific exceptions to replace broad 'except Exception'
patterns throughout the codebase, providing better error handling and debugging.
"""

from typing import Any, Dict, Optional


class MemorySystemError(Exception):
    """
    Base exception for all memory system errors.

    Provides common structure and context for all system-specific exceptions.
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
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
    """
    Raised when there are configuration-related errors.

    Examples:
    - Invalid environment variables
    - Missing required configuration
    - Configuration validation failures
    """

    pass


class DatabaseError(MemorySystemError):
    """
    Raised when database operations fail.

    Examples:
    - Qdrant connection failures
    - Kuzu query errors
    - Storage path issues
    - Collection creation failures
    """

    pass


class ProcessingError(MemorySystemError):
    """
    Raised when memory processing operations fail.

    Examples:
    - AI content analysis failures
    - Memory extraction errors
    - Type detection failures
    - Validation errors
    """

    pass


class NetworkError(MemorySystemError):
    """
    Raised when network/API operations fail.

    Examples:
    - Google API connectivity issues
    - Embedding generation failures
    - MCP server communication errors
    - Timeout errors
    """

    pass


class ValidationError(MemorySystemError):
    """
    Raised when data validation fails.

    Examples:
    - Schema validation errors
    - Model validation failures
    - Input format errors
    - Type checking failures
    """

    pass


class StorageError(DatabaseError):
    """
    Raised when storage operations fail.

    More specific than DatabaseError for storage-related issues.

    Examples:
    - File system errors
    - Permission issues
    - Disk space problems
    - Path access errors
    """

    pass


class EmbeddingError(NetworkError):
    """
    Raised when embedding generation fails.

    More specific than NetworkError for embedding-related issues.

    Examples:
    - Google embedding API failures
    - Invalid embedding dimensions
    - API key issues
    - Rate limiting
    """

    pass


class MCPError(MemorySystemError):
    """
    Raised when MCP (Model Context Protocol) operations fail.

    Examples:
    - MCP server startup failures
    - Tool execution errors
    - Protocol communication issues
    - Session management errors
    """

    pass


# Utility functions for error handling


def wrap_exception(
    original_error: Exception, operation: str, context: Optional[Dict[str, Any]] = None
) -> MemorySystemError:
    """
    Wrap a generic exception in an appropriate MemorySystemError subclass.

    Args:
        original_error: The original exception that was caught
        operation: Description of the operation that failed
        context: Additional context information

    Returns:
        Appropriate MemorySystemError subclass based on the original error
    """
    error_message = str(original_error)

    # Map common exceptions to our hierarchy
    if isinstance(original_error, (ConnectionError, TimeoutError)):
        return NetworkError(
            f"Network operation failed: {error_message}",
            operation=operation,
            context=context,
            original_error=original_error,
        )

    if isinstance(original_error, FileNotFoundError):
        return StorageError(
            f"File not found: {error_message}",
            operation=operation,
            context=context,
            original_error=original_error,
        )

    if isinstance(original_error, PermissionError):
        return StorageError(
            f"Permission denied: {error_message}",
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
    """
    Decorator for consistent error handling with context.

    Usage:
        @handle_with_context("memory_processing")
        def process_memory(self, content: str):
            # Implementation
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
                raise wrap_exception(e, operation, {"args": args, "kwargs": kwargs})

        return wrapper

    return decorator
