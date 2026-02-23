"""
Structured Logging Service.

Provides comprehensive structured logging with:
- UUID correlation IDs for request tracing
- JSON formatted logs for parsing
- Context propagation across services
- Performance metrics integration
- Log aggregation support (ELK, CloudWatch)
"""

import asyncio
import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from functools import wraps
from typing import Any

# Context variable for correlation ID
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Context variable for additional context
log_context_var: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "log_context", default={}
)


class LogLevel(str, Enum):
    """Log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: str
    level: str
    message: str
    correlation_id: str | None = None
    service: str = "bybit_strategy_tester"
    component: str | None = None
    operation: str | None = None
    duration_ms: float | None = None
    user_id: str | None = None
    request_id: str | None = None
    extra: dict = field(default_factory=dict)
    error: dict | None = None
    trace_id: str | None = None
    span_id: str | None = None


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Formats log records as JSON with correlation IDs and context.
    """

    def __init__(
        self,
        service_name: str = "bybit_strategy_tester",
        include_extra: bool = True,
    ):
        super().__init__()
        self.service_name = service_name
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get correlation ID from context
        correlation_id = correlation_id_var.get()
        context = log_context_var.get()

        # Build log entry
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": self.service_name,
        }

        # Add correlation ID if available
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add context fields
        if context:
            log_entry.update(context)

        # Add location info
        log_entry["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["error"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from record
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "message",
                    "taskName",
                ) and not key.startswith("_"):
                    log_entry[key] = value

        return json.dumps(log_entry, default=str)


class StructuredLoggingService:
    """
    Structured Logging Service.

    Provides utilities for structured logging with correlation IDs.
    """

    def __init__(
        self,
        service_name: str = "bybit_strategy_tester",
        default_level: LogLevel = LogLevel.INFO,
    ):
        self.service_name = service_name
        self.default_level = default_level
        self._configured = False
        self._handlers: list[logging.Handler] = []
        self._log_stats: dict[str, int] = {
            "debug": 0,
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0,
        }

    def configure_logging(
        self,
        level: LogLevel | None = None,
        json_output: bool = True,
        console_output: bool = True,
        file_output: str | None = None,
    ) -> None:
        """
        Configure structured logging.

        Args:
            level: Logging level
            json_output: Use JSON formatting
            console_output: Output to console
            file_output: Optional file path for log output
        """
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, (level or self.default_level).value))

        # Clear existing handlers
        root_logger.handlers = []

        # Create formatter
        if json_output:
            formatter = StructuredFormatter(service_name=self.service_name)
        else:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(correlation_id)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        # File handler
        if file_output:
            file_handler = logging.FileHandler(file_output)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        self._configured = True

    # ============================================================
    # Correlation ID Management
    # ============================================================

    @staticmethod
    def generate_correlation_id() -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())

    @staticmethod
    def get_correlation_id() -> str | None:
        """Get the current correlation ID."""
        return correlation_id_var.get()

    @staticmethod
    def set_correlation_id(correlation_id: str) -> str:
        """Set the correlation ID for the current context."""
        correlation_id_var.set(correlation_id)
        return correlation_id

    @staticmethod
    def clear_correlation_id() -> None:
        """Clear the correlation ID."""
        correlation_id_var.set(None)

    # ============================================================
    # Context Management
    # ============================================================

    @staticmethod
    def set_context(**kwargs: Any) -> None:
        """Set additional context for logging."""
        current = log_context_var.get()
        updated = {**current, **kwargs}
        log_context_var.set(updated)

    @staticmethod
    def get_context() -> dict:
        """Get current logging context."""
        return log_context_var.get()

    @staticmethod
    def clear_context() -> None:
        """Clear logging context."""
        log_context_var.set({})

    @staticmethod
    def add_to_context(key: str, value: Any) -> None:
        """Add a single key-value pair to context."""
        current = log_context_var.get()
        current[key] = value
        log_context_var.set(current)

    # ============================================================
    # Logging Helpers
    # ============================================================

    def log(
        self,
        level: LogLevel,
        message: str,
        component: str | None = None,
        operation: str | None = None,
        duration_ms: float | None = None,
        **extra: Any,
    ) -> None:
        """
        Log a structured message.

        Args:
            level: Log level
            message: Log message
            component: Component name
            operation: Operation name
            duration_ms: Duration in milliseconds
            **extra: Additional fields
        """
        logger = logging.getLogger(component or self.service_name)

        # Build extra dict
        log_extra = {}
        if component:
            log_extra["component"] = component
        if operation:
            log_extra["operation"] = operation
        if duration_ms is not None:
            log_extra["duration_ms"] = duration_ms
        log_extra.update(extra)

        # Add correlation ID
        correlation_id = self.get_correlation_id()
        if correlation_id:
            log_extra["correlation_id"] = correlation_id

        # Log at appropriate level
        log_method = getattr(logger, level.value.lower())
        log_method(message, extra=log_extra)

        # Update stats
        self._log_stats[level.value.lower()] += 1

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **kwargs)

    # ============================================================
    # Decorators
    # ============================================================

    def with_correlation_id(self, func: Callable) -> Callable:
        """Decorator to ensure correlation ID exists."""

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.get_correlation_id():
                self.set_correlation_id(self.generate_correlation_id())
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.get_correlation_id():
                self.set_correlation_id(self.generate_correlation_id())
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def log_execution(
        self,
        component: str | None = None,
        operation: str | None = None,
        log_args: bool = False,
        log_result: bool = False,
    ) -> Callable:
        """
        Decorator to log function execution with timing.

        Args:
            component: Component name
            operation: Operation name (defaults to function name)
            log_args: Whether to log function arguments
            log_result: Whether to log function result
        """

        def decorator(func: Callable) -> Callable:
            op_name = operation or func.__name__

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                extra = {}

                if log_args:
                    extra["args"] = str(args)[:200]
                    extra["kwargs"] = str(kwargs)[:200]

                self.info(
                    f"Starting {op_name}",
                    component=component,
                    operation=op_name,
                    **extra,
                )

                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000

                    result_extra = {"status": "success"}
                    if log_result:
                        result_extra["result"] = str(result)[:200]

                    self.info(
                        f"Completed {op_name}",
                        component=component,
                        operation=op_name,
                        duration_ms=duration_ms,
                        **result_extra,
                    )
                    return result

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self.error(
                        f"Failed {op_name}: {e}",
                        component=component,
                        operation=op_name,
                        duration_ms=duration_ms,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                    raise

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                extra = {}

                if log_args:
                    extra["args"] = str(args)[:200]
                    extra["kwargs"] = str(kwargs)[:200]

                self.info(
                    f"Starting {op_name}",
                    component=component,
                    operation=op_name,
                    **extra,
                )

                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000

                    result_extra = {"status": "success"}
                    if log_result:
                        result_extra["result"] = str(result)[:200]

                    self.info(
                        f"Completed {op_name}",
                        component=component,
                        operation=op_name,
                        duration_ms=duration_ms,
                        **result_extra,
                    )
                    return result

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000
                    self.error(
                        f"Failed {op_name}: {e}",
                        component=component,
                        operation=op_name,
                        duration_ms=duration_ms,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )
                    raise

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    # ============================================================
    # Statistics & Status
    # ============================================================

    def get_stats(self) -> dict:
        """Get logging statistics."""
        return {
            "configured": self._configured,
            "service_name": self.service_name,
            "default_level": self.default_level.value,
            "handlers_count": len(self._handlers),
            "log_counts": self._log_stats.copy(),
            "total_logs": sum(self._log_stats.values()),
        }

    def reset_stats(self) -> None:
        """Reset logging statistics."""
        self._log_stats = {
            "debug": 0,
            "info": 0,
            "warning": 0,
            "error": 0,
            "critical": 0,
        }


# Singleton instance
_structured_logging_service: StructuredLoggingService | None = None


def get_structured_logging_service() -> StructuredLoggingService:
    """Get or create structured logging service instance."""
    global _structured_logging_service
    if _structured_logging_service is None:
        _structured_logging_service = StructuredLoggingService()
        logging.getLogger(__name__).info("📝 Structured Logging Service initialized")
    return _structured_logging_service


# Convenience functions
def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return StructuredLoggingService.generate_correlation_id()


def get_correlation_id() -> str | None:
    """Get current correlation ID."""
    return StructuredLoggingService.get_correlation_id()


def set_correlation_id(correlation_id: str) -> str:
    """Set correlation ID."""
    return StructuredLoggingService.set_correlation_id(correlation_id)
