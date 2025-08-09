"""
Centralized logging configuration for the memory system.

This module provides consistent logging setup across all components,
replacing print() statements and providing structured logging.
"""

import logging
import os
from pathlib import Path
import sys


class MemorySystemLogger:
    """
    Centralized logger for the memory system with consistent formatting.

    Features:
    - Structured logging with context
    - File and console outputs
    - Log level management
    - Component-specific loggers
    """

    _loggers: dict[str, logging.Logger] = {}
    _configured = False

    @classmethod
    def setup_logging(
        cls,
        level: str = "INFO",
        log_file: str | None = None,
        console_output: bool = True,
        file_level: str | None = None,
    ) -> logging.Logger:
        """
        Configure centralized logging for the entire memory system.

        Args:
            level: Default logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional path to log file
            console_output: Whether to output to console
            file_level: Separate logging level for file (defaults to level)

        Returns:
            Main memory system logger
        """
        if cls._configured:
            return cls.get_logger("memory_system")

        # Create root logger for memory system
        root_logger = logging.getLogger("memory_system")
        root_logger.setLevel(logging.DEBUG)  # Capture all levels

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, level.upper()))
            console_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%H:%M:%S",
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        # File handler
        if log_file:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_file)
            file_level = file_level or level
            file_handler.setLevel(getattr(logging, file_level.upper()))
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

        cls._configured = True
        return root_logger

    @classmethod
    def get_logger(cls, component: str) -> logging.Logger:
        """
        Get or create a logger for a specific component.

        Args:
            component: Component name (e.g., "processor", "qdrant", "mcp_server")

        Returns:
            Logger instance for the component
        """
        logger_name = f"memory_system.{component}"

        if logger_name not in cls._loggers:
            logger = logging.getLogger(logger_name)
            cls._loggers[logger_name] = logger

            # If root logging not configured, use basic config
            if not cls._configured:
                cls.setup_logging()

        return cls._loggers.get(logger_name, logging.getLogger(logger_name))

    @classmethod
    def log_operation(cls, component: str, operation: str, level: str = "INFO", **context):
        """
        Log an operation with structured context.

        Args:
            component: Component performing the operation
            operation: Operation being performed
            level: Log level
            **context: Additional context as keyword arguments
        """
        logger = cls.get_logger(component)
        log_method = getattr(logger, level.lower())

        # Build context string
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message = f"[{operation}]"
        if context_str:
            message += f" {context_str}"

        log_method(message)

    @classmethod
    def log_performance(cls, component: str, operation: str, duration_ms: float, **context):
        """
        Log performance metrics for operations.

        Args:
            component: Component that performed the operation
            operation: Operation that was performed
            duration_ms: Duration in milliseconds
            **context: Additional context
        """
        logger = cls.get_logger(component)
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message = f"⚡ [{operation}] {duration_ms:.1f}ms"
        if context_str:
            message += f" | {context_str}"
        logger.info(message)

    @classmethod
    def log_error(cls, component: str, operation: str, error: Exception, **context):
        """
        Log errors with consistent formatting and context.

        Args:
            component: Component where error occurred
            operation: Operation that failed
            error: The exception that occurred
            **context: Additional context
        """
        logger = cls.get_logger(component)
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message = f"❌ [{operation}] {error.__class__.__name__}: {error}"
        if context_str:
            message += f" | {context_str}"
        logger.error(message, exc_info=True)


# Convenience functions for common logging patterns


def get_logger(component: str) -> logging.Logger:
    """Get a logger for a component. Convenience function."""
    return MemorySystemLogger.get_logger(component)


def setup_memory_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Setup memory system logging. Convenience function."""
    return MemorySystemLogger.setup_logging(level=level, log_file=log_file)


def log_operation(component: str, operation: str, **context):
    """Log an operation. Convenience function."""
    MemorySystemLogger.log_operation(component, operation, **context)


def log_performance(component: str, operation: str, duration_ms: float, **context):
    """Log performance metrics. Convenience function."""
    MemorySystemLogger.log_performance(component, operation, duration_ms, **context)


def log_error(component: str, operation: str, error: Exception, **context):
    """Log an error. Convenience function."""
    MemorySystemLogger.log_error(component, operation, error, **context)


# Auto-setup based on environment
def auto_setup_logging():
    """
    Automatically setup logging based on environment variables.

    Environment variables:
    - MEMORY_SYSTEM_LOG_LEVEL: Logging level (default: INFO)
    - MEMORY_SYSTEM_LOG_FILE: Log file path (optional)
    - MEMORY_SYSTEM_LOG_CONSOLE: Enable console output (default: true)
    """
    level = os.getenv("MEMORY_SYSTEM_LOG_LEVEL", "INFO")
    log_file = os.getenv("MEMORY_SYSTEM_LOG_FILE")
    console_output = os.getenv("MEMORY_SYSTEM_LOG_CONSOLE", "true").lower() == "true"

    return MemorySystemLogger.setup_logging(
        level=level, log_file=log_file, console_output=console_output
    )


# Initialize logging when module is imported
if not MemorySystemLogger._configured:
    auto_setup_logging()
