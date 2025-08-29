"""Centralized logging configuration for the memory system."""

import logging
from pathlib import Path
import sys


class MemorySystemLogger:
    """Centralized logger for the memory system.

    Attributes:
        _loggers: Cache of created loggers by component name.
        _configured: Whether logging has been configured.
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
        """Configure centralized logging for the entire memory system.

        Args:
            level: Console logging level.
            log_file: Optional log file path.
            console_output: Whether to enable console logging.
            file_level: Optional file logging level (defaults to console level).

        Returns:
            logging.Logger: Root logger instance.
        """
        if cls._configured:
            return cls.get_logger("memg_core")

        # Create root logger for memory system
        root_logger = logging.getLogger("memg_core")
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
        """Get or create a logger for a specific component.

        Args:
            component: Component name for the logger.

        Returns:
            logging.Logger: Logger instance for the component.
        """
        logger_name = f"memg_core.{component}"

        if logger_name not in cls._loggers:
            logger = logging.getLogger(logger_name)
            cls._loggers[logger_name] = logger

            # If root logging not configured, use basic config
            if not cls._configured:
                cls.setup_logging()

        return cls._loggers.get(logger_name, logging.getLogger(logger_name))

    @classmethod
    def log_operation(cls, component: str, operation: str, level: str = "INFO", **context):
        """Log an operation with structured context.

        Args:
            component: Component name.
            operation: Operation being performed.
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            **context: Additional context key-value pairs.
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
        """Log performance metrics for operations.

        Args:
            component: Component name.
            operation: Operation being measured.
            duration_ms: Duration in milliseconds.
            **context: Additional context key-value pairs.
        """
        logger = cls.get_logger(component)
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message = f"⚡ [{operation}] {duration_ms:.1f}ms"
        if context_str:
            message += f" | {context_str}"
        logger.info(message)

    @classmethod
    def log_error(cls, component: str, operation: str, error: Exception, **context):
        """Log errors with consistent formatting and context.

        Args:
            component: Component name.
            operation: Operation that failed.
            error: Exception that occurred.
            **context: Additional context key-value pairs.
        """
        logger = cls.get_logger(component)
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message = f"❌ [{operation}] {error.__class__.__name__}: {error}"
        if context_str:
            message += f" | {context_str}"
        logger.error(message, exc_info=True)


# Convenience functions for common logging patterns
def get_logger(component: str) -> logging.Logger:
    """Get a logger for a component.

    Args:
        component: Component name.

    Returns:
        logging.Logger: Logger instance for the component.
    """
    return MemorySystemLogger.get_logger(component)


def setup_memory_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
    """Setup memory system logging.

    Args:
        level: Logging level.
        log_file: Optional log file path.

    Returns:
        logging.Logger: Root logger instance.
    """
    return MemorySystemLogger.setup_logging(level=level, log_file=log_file)


def log_operation(component: str, operation: str, **context):
    """Log an operation.

    Args:
        component: Component name.
        operation: Operation being performed.
        **context: Additional context key-value pairs.
    """
    MemorySystemLogger.log_operation(component, operation, **context)


def log_performance(component: str, operation: str, duration_ms: float, **context):
    """Log performance metrics.

    Args:
        component: Component name.
        operation: Operation being measured.
        duration_ms: Duration in milliseconds.
        **context: Additional context key-value pairs.
    """
    MemorySystemLogger.log_performance(component, operation, duration_ms, **context)


def log_error(component: str, operation: str, error: Exception, **context):
    """Log an error.

    Args:
        component: Component name.
        operation: Operation that failed.
        error: Exception that occurred.
        **context: Additional context key-value pairs.
    """
    MemorySystemLogger.log_error(component, operation, error, **context)
