"""Minimal database wiring for local development and tests.

Exports:
 - engine: SQLAlchemy Engine
 - SessionLocal: sessionmaker() configured
 - Base: declarative base for models
 - get_db: FastAPI dependency generator

Behavior:
 - Reads DATABASE_URL from env; if missing, falls back to in-memory SQLite for safe imports.
 - Designed to be minimal and non-invasive; replace with production DB config when available.
"""

import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Read DATABASE_URL from environment; fallback to data.sqlite3 for local dev
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    # Use local SQLite file instead of in-memory for persistence
    import pathlib

    project_root = pathlib.Path(__file__).parent.parent.parent
    sqlite_path = project_root / "data.sqlite3"
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    logger.info(f"DATABASE_URL not set; using local SQLite: {sqlite_path}")

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
else:
    engine = create_engine(DATABASE_URL)

# SessionLocal factory
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=Session
)

# Base declarative
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and ensures close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["engine", "SessionLocal", "Base", "get_db", "DATABASE_URL"]


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
