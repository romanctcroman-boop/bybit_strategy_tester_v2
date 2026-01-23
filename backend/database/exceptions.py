"""
Database Exceptions

Custom exceptions for database operations with proper context
and classification for error handling strategies.
"""

from typing import Optional


class DatabaseError(Exception):
    """
    Base exception for all database-related errors.

    Provides consistent error context including:
    - Operation that failed
    - Entity/table involved
    - Original exception cause
    """

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        entity: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.operation = operation
        self.entity = entity
        self.cause = cause
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.append(f"[operation={self.operation}]")
        if self.entity:
            parts.append(f"[entity={self.entity}]")
        return " ".join(parts)

    def is_retryable(self) -> bool:
        """Check if this error type can be retried."""
        return False


class ConnectionError(DatabaseError):
    """Database connection failed or was lost."""

    def is_retryable(self) -> bool:
        return True


class QueryError(DatabaseError):
    """Query execution failed."""

    pass


class IntegrityError(DatabaseError):
    """Data integrity constraint was violated."""

    pass


class DuplicateKeyError(IntegrityError):
    """Attempted to insert a duplicate key."""

    pass


class TimeoutError(DatabaseError):
    """Database operation timed out."""

    def is_retryable(self) -> bool:
        return True


class LockError(DatabaseError):
    """Database lock could not be acquired."""

    def is_retryable(self) -> bool:
        return True


class NotFoundError(DatabaseError):
    """Requested entity was not found."""

    pass


class TransactionError(DatabaseError):
    """Transaction commit or rollback failed."""

    pass


def classify_sqlalchemy_error(
    error: Exception,
    operation: str = "unknown",
    entity: str = "unknown",
) -> DatabaseError:
    """
    Convert SQLAlchemy exceptions to our custom exceptions.

    This provides consistent error types across the application
    regardless of the underlying database driver.

    Args:
        error: Original SQLAlchemy or database error
        operation: Name of the operation that failed
        entity: Name of the entity/table involved

    Returns:
        Appropriate DatabaseError subclass
    """
    from sqlalchemy.exc import (
        DatabaseError as SADatabaseError,
    )
    from sqlalchemy.exc import (
        IntegrityError as SAIntegrityError,
    )
    from sqlalchemy.exc import (
        OperationalError,
    )
    from sqlalchemy.exc import (
        TimeoutError as SATimeoutError,
    )

    error_str = str(error).lower()

    # Connection errors
    if isinstance(error, OperationalError):
        if "locked" in error_str or "busy" in error_str:
            return LockError(
                f"Database locked during {operation}",
                operation=operation,
                entity=entity,
                cause=error,
            )
        if "connection" in error_str or "unable to open" in error_str:
            return ConnectionError(
                f"Connection failed during {operation}",
                operation=operation,
                entity=entity,
                cause=error,
            )
        if "timeout" in error_str:
            return TimeoutError(
                f"Timeout during {operation}",
                operation=operation,
                entity=entity,
                cause=error,
            )

    # Integrity errors
    if isinstance(error, SAIntegrityError):
        if "unique" in error_str or "duplicate" in error_str:
            return DuplicateKeyError(
                f"Duplicate key in {operation}",
                operation=operation,
                entity=entity,
                cause=error,
            )
        return IntegrityError(
            f"Integrity constraint violated in {operation}",
            operation=operation,
            entity=entity,
            cause=error,
        )

    # Timeout errors
    if isinstance(error, SATimeoutError):
        return TimeoutError(
            f"Operation timed out: {operation}",
            operation=operation,
            entity=entity,
            cause=error,
        )

    # Generic database errors
    if isinstance(error, SADatabaseError):
        return QueryError(
            f"Query failed during {operation}: {error}",
            operation=operation,
            entity=entity,
            cause=error,
        )

    # Fallback for unknown errors
    return DatabaseError(
        f"Database error during {operation}: {error}",
        operation=operation,
        entity=entity,
        cause=error,
    )
