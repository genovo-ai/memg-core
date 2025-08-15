# `memg_core/core/exceptions.py`

## Module Description
This module defines a custom exception hierarchy for the MEMG memory system. It provides specific exception classes for different types of errors (e.g., configuration, database, validation, processing) and utility functions for wrapping generic exceptions with more context.

## Internal Dependencies
- None

## Classes

### `MemorySystemError`
- **Description**: Base exception for all errors within the memory system. It extends Python's `Exception` and allows for storing additional context such as the operation being performed and the original error that caused it.
- **Attributes**:
  - `message`: `str` - The main error message.
  - `operation`: `str | None` - The name of the operation during which the error occurred.
  - `context`: `dict[str, Any]` - A dictionary providing additional context about the error.
  - `original_error`: `Exception | None` - The original exception that triggered this error.
- **Methods**:
  - `__init__`:
    - **Description**: Initializes the `MemorySystemError` instance with a message, optional operation, context, and original error.
    - **Inputs**:
      - `message`: `str` - The primary error message.
      - `operation`: `str | None` = None - The operation name.
      - `context`: `dict[str, Any] | None` = None - Additional context as a dictionary.
      - `original_error`: `Exception | None` = None - The underlying exception.
    - **Returns**: None
    - **Schema**:
      - Input: `message` (String), `operation` (String or None), `context` (Dictionary with Any type values or None), `original_error` (Exception Object or None)
      - Output: None
      - Type Mixing: Mixed type (input `context`, `original_error`)

### `ConfigurationError`
- **Description**: A subclass of `MemorySystemError` specifically for errors related to configuration, such as invalid environment variables or configuration validation failures.

### `DatabaseError`
- **Description**: A subclass of `MemorySystemError` for failures during database operations, covering issues with Qdrant or Kuzu interactions.

### `ValidationError`
- **Description**: A subclass of `MemorySystemError` for errors arising from data validation failures, such as schema mismatches or invalid input formats.

### `ProcessingError`
- **Description**: A subclass of `MemorySystemError` serving as a catch-all for failures that occur during memory processing operations within the pipeline.

## Functions

### `wrap_exception`
- **Description**: Wraps a generic Python exception in an appropriate `MemorySystemError` subclass based on the type of the original error. It maps common exceptions like `FileNotFoundError`, `PermissionError`, and `ValueError` to specific `MemorySystemError` types.
- **Inputs**:
  - `original_error`: `Exception` - The exception to be wrapped.
  - `operation`: `str` - The name of the operation where the error occurred.
  - `context`: `dict[str, Any] | None` = None - Optional additional context for the error.
- **Returns**: `memg_core.core.exceptions.MemorySystemError` - An instance of a `MemorySystemError` subclass.
- **Schema**:
  - Input: `original_error` (Exception Object), `operation` (String), `context` (Dictionary with Any type values or None)
  - Output: `MemorySystemError` (MemorySystemError Object)
  - Type Mixing: Mixed type (input `context`, output `MemorySystemError` which can have mixed context)

### `handle_with_context`
- **Description**: A decorator that provides consistent error handling by wrapping function executions. It catches exceptions, re-raises `MemorySystemError` instances as-is, and wraps other unknown exceptions using `wrap_exception`, adding contextual information.
- **Inputs**:
  - `operation`: `str` - The name of the operation to be used in error messages.
- **Returns**: `Callable` - A decorator function.
- **Schema**:
  - Input: `operation` (String)
  - Output: `Callable` (Callable Object)
  - Type Mixing: Defined type
