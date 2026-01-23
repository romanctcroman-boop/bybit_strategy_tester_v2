"""
Unit of Work Pattern - Transaction Management

Provides atomic transaction handling across multiple repositories.
Ensures data consistency with automatic commit/rollback.

Usage:
    from backend.database.unit_of_work import UnitOfWork
    from backend.database.repository import KlineRepository

    # As context manager (recommended):
    with UnitOfWork() as uow:
        repo = KlineRepository(uow.session)
        repo.bulk_upsert('BTCUSDT', '15', candles)
        # Auto-commit on success, auto-rollback on exception

    # Manual control:
    uow = UnitOfWork()
    uow.begin()
    try:
        repo = KlineRepository(uow.session)
        repo.bulk_upsert('BTCUSDT', '15', candles)
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.close()
"""

import logging
from contextlib import contextmanager
from typing import Callable, Optional, TypeVar

from sqlalchemy.orm import Session

from backend.database import SessionLocal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class UnitOfWork:
    """
    Unit of Work pattern for transaction management.

    Features:
    - Automatic commit on successful exit
    - Automatic rollback on exception
    - Supports nested transactions (savepoints)
    - Works with multiple repositories

    Attributes:
        session: SQLAlchemy Session for database operations
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], Session]] = None,
    ):
        """
        Initialize Unit of Work.

        Args:
            session_factory: Optional custom session factory.
                           Defaults to SessionLocal from backend.database
        """
        self.session_factory = session_factory or SessionLocal
        self.session: Optional[Session] = None
        self._is_nested = False

    def __enter__(self) -> "UnitOfWork":
        """Enter context manager - begin transaction."""
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - commit or rollback."""
        if exc_type is not None:
            # Exception occurred - rollback
            logger.debug(f"UnitOfWork rollback due to: {exc_type.__name__}: {exc_val}")
            self.rollback()
        else:
            # Success - commit
            self.commit()

        self.close()

        # Don't suppress exceptions
        return False

    def begin(self) -> "UnitOfWork":
        """
        Begin a new transaction.

        Creates a new session if one doesn't exist.
        """
        if self.session is None:
            self.session = self.session_factory()
            logger.debug("UnitOfWork: new session created")
        return self

    def commit(self) -> None:
        """
        Commit the current transaction.

        Flushes pending changes and commits to database.
        """
        if self.session:
            try:
                self.session.commit()
                logger.debug("UnitOfWork: committed")
            except Exception as e:
                logger.error(f"UnitOfWork commit failed: {e}")
                self.rollback()
                raise

    def rollback(self) -> None:
        """
        Rollback the current transaction.

        Discards all pending changes.
        """
        if self.session:
            try:
                self.session.rollback()
                logger.debug("UnitOfWork: rolled back")
            except Exception as e:
                logger.error(f"UnitOfWork rollback failed: {e}")

    def close(self) -> None:
        """
        Close the session.

        Releases database connection back to pool.
        """
        if self.session:
            try:
                self.session.close()
                logger.debug("UnitOfWork: session closed")
            except Exception as e:
                logger.error(f"UnitOfWork close failed: {e}")
            finally:
                self.session = None

    def flush(self) -> None:
        """
        Flush pending changes to database.

        Sends SQL statements but doesn't commit.
        Useful for getting auto-generated IDs.
        """
        if self.session:
            self.session.flush()

    @contextmanager
    def savepoint(self):
        """
        Create a savepoint for nested transaction.

        Usage:
            with UnitOfWork() as uow:
                repo.add(entity1)
                with uow.savepoint():
                    repo.add(entity2)  # Can be rolled back independently
        """
        if not self.session:
            raise RuntimeError("No active session for savepoint")

        nested = self.session.begin_nested()
        try:
            yield nested
            nested.commit()
        except Exception:
            nested.rollback()
            raise


@contextmanager
def unit_of_work(session_factory: Optional[Callable[[], Session]] = None):
    """
    Functional context manager for Unit of Work.

    Usage:
        with unit_of_work() as uow:
            repo = KlineRepository(uow.session)
            repo.bulk_upsert('BTCUSDT', '15', candles)
    """
    uow = UnitOfWork(session_factory)
    try:
        with uow as u:
            yield u
    except Exception:
        raise


class ReadOnlyUnitOfWork(UnitOfWork):
    """
    Read-only Unit of Work that never commits.

    Use for queries where you want transaction isolation
    but don't intend to modify data.

    Usage:
        with ReadOnlyUnitOfWork() as uow:
            repo = KlineRepository(uow.session)
            data = repo.get_klines('BTCUSDT', '15')
    """

    def commit(self) -> None:
        """Override commit to always rollback (read-only)."""
        self.rollback()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Always rollback on exit."""
        self.rollback()
        self.close()
        return False
