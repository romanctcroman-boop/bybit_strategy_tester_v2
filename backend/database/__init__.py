"""Minimal database wiring for local development and tests.

Exports:
 - engine: SQLAlchemy Engine
 - SessionLocal: sessionmaker() configured
 - Base: declarative base for models
 - get_db: FastAPI dependency generator

Behavior:
 - Reads DATABASE_URL from env; if missing, falls back to in-memory SQLite for safe imports.
 - In production/staging, raises error if DATABASE_URL is not set.
 - Designed to be minimal and non-invasive; replace with production DB config when available.
"""

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Environment detection
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

# Read DATABASE_URL from environment; fallback to data.sqlite3 for local dev
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Production/Staging check - require explicit DATABASE_URL
    if ENVIRONMENT in ("production", "staging"):
        raise RuntimeError(
            f"DATABASE_URL must be set in {ENVIRONMENT} environment! "
            "Example: postgresql://user:pass@host:5432/dbname or "
            "mysql://user:pass@host:3306/dbname"
        )

    # Development fallback to local SQLite file
    import pathlib

    project_root = pathlib.Path(__file__).parent.parent.parent
    sqlite_path = project_root / "data.sqlite3"
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    logger.warning(
        f"DATABASE_URL not set; using local SQLite: {sqlite_path} (OK for development, NOT suitable for production)"
    )

# Use future engines compatible with SQLAlchemy 1.4+ behavior
if DATABASE_URL.startswith("sqlite"):
    # For in-memory sqlite use StaticPool so multiple connections share the same DB.
    if DATABASE_URL == "sqlite:///:memory:":
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif DATABASE_URL.startswith("postgresql"):
    # PostgreSQL with connection pooling best practices
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,  # Number of persistent connections
        max_overflow=10,  # Additional connections beyond pool_size
        pool_timeout=30,  # Seconds to wait for connection from pool
        pool_recycle=1800,  # Recycle connections after 30 minutes (avoid stale connections)
        pool_pre_ping=True,  # Verify connection is alive before using
        echo=ENVIRONMENT == "development",  # SQL logging in dev only
    )
    logger.info("PostgreSQL engine created with pool_size=5, pool_recycle=1800s, pool_pre_ping=True")
elif DATABASE_URL.startswith("mysql"):
    # MySQL with connection pooling best practices
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=3600,  # MySQL default wait_timeout is 8 hours, but play safe
        pool_pre_ping=True,
        echo=ENVIRONMENT == "development",
    )
    logger.info("MySQL engine created with pool_size=5, pool_recycle=3600s, pool_pre_ping=True")
else:
    # Generic engine for other databases
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Always verify connections
        echo=ENVIRONMENT == "development",
    )
    logger.info(f"Generic engine created for: {DATABASE_URL.split('://')[0]}")

# SessionLocal factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

# Base declarative
Base = declarative_base()


def get_db() -> Generator[Session]:
    """FastAPI dependency that yields a DB session and ensures close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["DATABASE_URL", "Base", "SessionLocal", "engine", "get_db", "get_pool_status"]


def get_pool_status() -> dict:
    """Get connection pool status for monitoring.

    Returns:
        dict with pool statistics (size, checkedout, overflow, checkedin)
        or empty dict for SQLite (no pool monitoring).
    """
    if DATABASE_URL.startswith("sqlite"):
        return {"pool_type": "sqlite", "message": "SQLite doesn't use connection pooling"}

    try:
        pool = engine.pool
        return {
            "pool_type": type(pool).__name__,
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "checked_in": pool.checkedin(),
            "invalidated": getattr(pool, "_invalidate_time", None),
        }
    except Exception as e:
        logger.warning(f"Failed to get pool status: {e}")
        return {"error": str(e)}


# Lazy imports for repository and unit of work
# (avoid circular imports by importing when needed)
def get_unit_of_work():
    """Get UnitOfWork class for transaction management."""
    from .unit_of_work import UnitOfWork

    return UnitOfWork


def get_kline_repository():
    """Get KlineRepository class for kline data access."""
    from .repository import KlineRepository

    return KlineRepository


def get_sqlite_pool():
    """Get SQLiteConnectionPool for efficient connection reuse."""
    from .sqlite_pool import SQLiteConnectionPool

    return SQLiteConnectionPool


def get_kline_archiver():
    """Get KlineArchiver for time-based data partitioning."""
    from .partitioning import KlineArchiver

    return KlineArchiver


def get_unified_kline_query():
    """Get UnifiedKlineQuery for querying across partitions."""
    from .partitioning import UnifiedKlineQuery

    return UnifiedKlineQuery


def get_retry_decorator():
    """Get with_db_retry decorator for retry logic."""
    from .retry import with_db_retry

    return with_db_retry
