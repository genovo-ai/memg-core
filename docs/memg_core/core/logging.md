# `memg_core/core/logging.py`

## Module Description
This module provides a centralized logging configuration for the MEMG memory system. It offers a `MemorySystemLogger` class for setting up and managing loggers, along with convenience functions for logging operations, performance metrics, and errors with consistent formatting and contextual information.

## Internal Dependencies
- None

## External Dependencies
- `logging`: Python's standard logging library.
- `pathlib`: `Path` for handling file paths.
- `sys`: For interacting with the Python interpreter, specifically `sys.stdout` for console logging.

## Classes

### `MemorySystemLogger`
- **Description**: A class that manages the centralized logging for the MEMG system. It allows for configuring root and component-specific loggers, handling console and file output, and providing structured logging for various event types.
- **Attributes**:
  - `_loggers`: dict[str, logging.Logger] - A class-level dictionary to store created logger instances, keyed by their full names.
  - `_configured`: bool - A class-level flag indicating whether the root logger has been configured.
- **Methods**:
  - `setup_logging` (classmethod):
    - **Description**: Configures the centralized logging for the entire memory system. It creates and configures a root logger (`memg_core`) with optional console and file handlers. It ensures that logging is configured only once.
    - **Inputs**:
      - `level`: str = "INFO" - The default logging level for console output (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
      - `log_file`: str | None = None - Optional path to a log file. If provided, logs will also be written to this file.
      - `console_output`: bool = True - If True, logs will be printed to the console.
      - `file_level`: str | None = None - Optional logging level specifically for the file output. Defaults to `level` if not provided.
    - **Returns**: `logging.Logger` - The root logger instance for `memg_core`.
  - `get_logger` (classmethod):
    - **Description**: Retrieves an existing logger for a specific component or creates a new one if it doesn't exist. If the root logger hasn't been configured, it calls `setup_logging` to perform a basic configuration.
    - **Inputs**:
      - `component`: str - The name of the component for which to get the logger (e.g., "api", "core.pipeline").
    - **Returns**: `logging.Logger` - The logger instance for the specified component.
  - `log_operation` (classmethod):
    - **Description**: Logs a general operation with structured context. The log message includes the operation name and a pipe-separated list of context key-value pairs.
    - **Inputs**:
      - `component`: str - The component logging the operation.
      - `operation`: str - A descriptive name for the operation.
      - `level`: str = "INFO" - The logging level for this message (e.g., "INFO", "DEBUG").
      - `**context`: Any - Arbitrary keyword arguments representing contextual information.
    - **Returns**: None
  - `log_performance` (classmethod):
    - **Description**: Logs performance metrics for operations, including the duration in milliseconds and any additional context. Messages are prefixed with a '⚡' symbol.
    - **Inputs**:
      - `component`: str - The component logging the performance.
      - `operation`: str - The name of the operation measured.
      - `duration_ms`: float - The duration of the operation in milliseconds.
      - `**context`: Any - Arbitrary keyword arguments for additional context.
    - **Returns**: None
  - `log_error` (classmethod):
    - **Description**: Logs error messages with consistent formatting, including the exception type and message, and additional context. Errors are logged with `logging.ERROR` level and `exc_info=True` for traceback inclusion.
    - **Inputs**:
      - `component`: str - The component where the error occurred.
      - `operation`: str - The name of the operation that failed.
      - `error`: Exception - The exception object caught.
      - `**context`: Any - Arbitrary keyword arguments for additional context.
    - **Returns**: None

## Functions

### `get_logger`
- **Description**: Convenience function to get a logger instance for a given component.
- **Inputs**:
  - `component`: str - The component name.
- **Returns**: `logging.Logger` - The logger instance.

### `setup_memory_logging`
- **Description**: Convenience function to set up the memory system's logging, forwarding parameters to `MemorySystemLogger.setup_logging`.
- **Inputs**:
  - `level`: str = "INFO" - The default logging level.
  - `log_file`: str | None = None - Optional path to a log file.
- **Returns**: `logging.Logger` - The root logger instance.

### `log_operation`
- **Description**: Convenience function to log an operation with context, forwarding parameters to `MemorySystemLogger.log_operation`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `**context`: Any - Additional context.
- **Returns**: None

### `log_performance`
- **Description**: Convenience function to log performance metrics, forwarding parameters to `MemorySystemLogger.log_performance`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `duration_ms`: float - The duration in milliseconds.
  - `**context`: Any - Additional context.
- **Returns**: None

### `log_error`
- **Description**: Convenience function to log errors with context, forwarding parameters to `MemorySystemLogger.log_error`.
- **Inputs**:
  - `component`: str - The component name.
  - `operation`: str - The operation name.
  - `error`: Exception - The exception object.
  - `**context`: Any - Additional context.
- **Returns**: None
