"""
Retry Logic for Database Operations.

Provides decorators and utilities for handling transient database errors
like deadlocks, lock timeouts, and connection issues.

Uses tenacity library for configurable retry behavior with exponential backoff.

Usage:
    from backend.database.retry import with_db_retry, RetryConfig

    @with_db_retry()
    def my_db_operation():
        # Your database code here
        pass

    # Or with custom config:
    @with_db_retry(RetryConfig(max_attempts=5, max_delay=10.0))
    def critical_operation():
        pass
"""

import functools
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

try:
    from tenacity import (
        RetryError,
        before_sleep_log,
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    RetryError = Exception

logger = logging.getLogger(__name__)

# Type variable for generic function
F = TypeVar("F", bound=Callable[..., Any])


# SQLite error codes that indicate transient/retryable errors
SQLITE_RETRYABLE_CODES = {
    5,  # SQLITE_BUSY
    6,  # SQLITE_LOCKED
    261,  # SQLITE_BUSY_RECOVERY
    262,  # SQLITE_LOCKED_SHAREDCACHE
    517,  # SQLITE_BUSY_SNAPSHOT
    518,  # SQLITE_LOCKED_VTAB
}

# SQLAlchemy/generic retryable exceptions
RETRYABLE_MESSAGES = {
    "database is locked",
    "database table is locked",
    "deadlock detected",
    "lock wait timeout",
    "could not serialize access",
    "concurrent update",
    "connection reset",
    "broken pipe",
    "server closed the connection",
}


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 0.1  # seconds
    max_delay: float = 5.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True

    # Which exceptions to retry
    retry_on: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            sqlite3.OperationalError,
            sqlite3.DatabaseError,
        )
    )

    # Custom error checker (optional)
    should_retry_func: Callable[[Exception], bool] | None = None


class RetryMetrics:
    """Metrics for retry operations."""

    def __init__(self):
        self.total_attempts = 0
        self.successful_retries = 0
        self.failed_retries = 0
        self.total_retry_time_ms = 0.0

    def record_attempt(self, attempt: int, duration_ms: float, success: bool):
        """Record a retry attempt."""
        self.total_attempts += 1
        self.total_retry_time_ms += duration_ms
        if attempt > 1:  # Retry (not first attempt)
            if success:
                self.successful_retries += 1
            else:
                self.failed_retries += 1

    def get_stats(self) -> dict:
        """Get retry statistics."""
        return {
            "total_attempts": self.total_attempts,
            "successful_retries": self.successful_retries,
            "failed_retries": self.failed_retries,
            "avg_time_ms": self.total_retry_time_ms / self.total_attempts
            if self.total_attempts > 0
            else 0,
        }


# Global metrics
_retry_metrics = RetryMetrics()


def is_retryable_error(exc: Exception) -> bool:
    """
    Check if an exception is retryable.

    Args:
        exc: The exception to check

    Returns:
        True if the error is transient and should be retried
    """
    # Check SQLite error codes
    if isinstance(exc, sqlite3.OperationalError):
        # Get error code if available
        args = exc.args
        if args:
            error_msg = str(args[0]).lower()
            for msg in RETRYABLE_MESSAGES:
                if msg in error_msg:
                    return True
        return True  # Default to retry for OperationalError

    if isinstance(exc, sqlite3.DatabaseError):
        error_msg = str(exc).lower()
        for msg in RETRYABLE_MESSAGES:
            if msg in error_msg:
                return True

    # Check SQLAlchemy exceptions
    exc_type_name = type(exc).__name__
    if exc_type_name in ("OperationalError", "DatabaseError", "InterfaceError"):
        error_msg = str(exc).lower()
        for msg in RETRYABLE_MESSAGES:
            if msg in error_msg:
                return True

    return False


def with_db_retry(
    config: RetryConfig | None = None,
    logger: logging.Logger | None = None,
) -> Callable[[F], F]:
    """
    Decorator for retrying database operations with exponential backoff.

    Usage:
        @with_db_retry()
        def get_data():
            # database operations
            pass

        @with_db_retry(RetryConfig(max_attempts=5))
        def critical_operation():
            pass
    """
    if config is None:
        config = RetryConfig()

    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        if TENACITY_AVAILABLE:
            # Use tenacity for sophisticated retry logic
            @retry(
                retry=retry_if_exception_type(config.retry_on),
                stop=stop_after_attempt(config.max_attempts),
                wait=wait_exponential(
                    multiplier=config.initial_delay,
                    max=config.max_delay,
                    exp_base=config.exponential_base,
                ),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper  # type: ignore
        else:
            # Fallback implementation without tenacity
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                delay = config.initial_delay

                for attempt in range(1, config.max_attempts + 1):
                    start_time = time.perf_counter()
                    try:
                        result = func(*args, **kwargs)
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        _retry_metrics.record_attempt(
                            attempt, duration_ms, success=True
                        )
                        return result

                    except config.retry_on as e:
                        duration_ms = (time.perf_counter() - start_time) * 1000
                        _retry_metrics.record_attempt(
                            attempt, duration_ms, success=False
                        )

                        last_exception = e

                        # Check if we should retry
                        if config.should_retry_func and not config.should_retry_func(e):
                            raise

                        if attempt < config.max_attempts:
                            logger.warning(
                                f"Retry {attempt}/{config.max_attempts} for {func.__name__}: {e}"
                            )

                            # Add jitter if enabled
                            actual_delay = delay
                            if config.jitter:
                                import random

                                actual_delay = delay * (0.5 + random.random())

                            time.sleep(actual_delay)
                            delay = min(
                                delay * config.exponential_base, config.max_delay
                            )
                        else:
                            logger.error(
                                f"All {config.max_attempts} attempts failed for {func.__name__}: {e}"
                            )

                raise last_exception  # type: ignore

            return wrapper  # type: ignore

    return decorator


def retry_on_lock(
    max_attempts: int = 3,
    initial_delay: float = 0.1,
) -> Callable[[F], F]:
    """
    Simplified decorator specifically for SQLite lock errors.

    Usage:
        @retry_on_lock()
        def write_to_db():
            # Your write operation
            pass
    """
    return with_db_retry(
        RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            retry_on=(sqlite3.OperationalError,),
            should_retry_func=is_retryable_error,
        )
    )


def get_retry_metrics() -> dict:
    """Get global retry metrics."""
    return _retry_metrics.get_stats()


def reset_retry_metrics():
    """Reset global retry metrics."""
    global _retry_metrics
    _retry_metrics = RetryMetrics()


# Context manager for retryable transactions
class RetryableTransaction:
    """
    Context manager for retryable database transactions.

    Usage:
        with RetryableTransaction(connection) as tx:
            tx.execute("INSERT INTO ...")
            tx.execute("UPDATE ...")
        # Automatically commits or rolls back with retry
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        config: RetryConfig | None = None,
    ):
        self.connection = connection
        self.config = config or RetryConfig()
        self.cursor: sqlite3.Cursor | None = None
        self._in_transaction = False

    def __enter__(self):
        self.cursor = self.connection.cursor()
        self._in_transaction = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success - commit with retry
            self._commit_with_retry()
        else:
            # Error - rollback
            try:
                self.connection.rollback()
            except Exception:
                pass

        self._in_transaction = False
        if self.cursor:
            self.cursor.close()

        return False  # Don't suppress exceptions

    @with_db_retry()
    def _commit_with_retry(self):
        """Commit with retry on lock."""
        self.connection.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL with the transaction cursor."""
        if self.cursor is None:
            raise RuntimeError("Not in transaction context")
        return self.cursor.execute(sql, params)

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """Execute SQL for multiple parameter sets."""
        if self.cursor is None:
            raise RuntimeError("Not in transaction context")
        return self.cursor.executemany(sql, params_list)
