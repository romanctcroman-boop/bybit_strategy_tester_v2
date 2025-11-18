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
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# Load .env file for local development
try:
    from pathlib import Path

    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip()
except Exception:
    pass

logger = logging.getLogger(__name__)

# Read DATABASE_URL from environment; fallback to in-memory sqlite
DATABASE_URL = os.environ.get("DATABASE_URL")


# Sanitize DATABASE_URL to avoid hidden unicode whitespace (e.g. NBSP \u00A0) from shells/copy-paste
def _sanitize_url(url: str) -> str:
    try:
        # Common problematic unicode spaces that may sneak in
        bad_spaces = ["\u00a0", "\u2007", "\u202f"]
        for ch in bad_spaces:
            url = url.replace(ch, "")
        return url.strip()
    except Exception:
        return url


if DATABASE_URL:
    DATABASE_URL = _sanitize_url(DATABASE_URL)
    # mirror sanitized value back into env for any late readers
    os.environ["DATABASE_URL"] = DATABASE_URL
else:
    logger.warning("DATABASE_URL not set; using in-memory sqlite for local imports/tests")
    DATABASE_URL = "sqlite:///:memory:"

# Use future engines compatible with SQLAlchemy 1.4+ behavior
if DATABASE_URL.startswith("sqlite"):
    # Python 3.12+: register explicit adapters to silence deprecated default datetime adapter
    try:
        import sqlite3
        from datetime import datetime as _dt

        # Store datetimes as ISO strings; SQLAlchemy will handle reading where needed
        sqlite3.register_adapter(_dt, lambda v: v.isoformat(sep=" ", timespec="seconds"))
        # Enable type detection (optional; helps when selecting DATETIME columns)
        _detect = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    except Exception:
        sqlite3 = None  # type: ignore
        _detect = None  # type: ignore

    # For in-memory sqlite use StaticPool so multiple connections share the same DB.
    if DATABASE_URL == "sqlite:///:memory:":
        engine = create_engine(
            DATABASE_URL,
            connect_args={
                "check_same_thread": False,
                **({"detect_types": _detect} if _detect else {}),
            },
            poolclass=StaticPool,
            echo=False,
            pool_pre_ping=False,
            pool_recycle=3600,
        )
    else:
        engine = create_engine(
            DATABASE_URL,
            connect_args={
                "check_same_thread": False,
                **({"detect_types": _detect} if _detect else {}),
            },
            pool_recycle=3600,
        )
else:
    # Week 1, Day 3: Enhanced Connection Pooling for Production
    # Prefer psycopg (psycopg3) driver on Windows/Python 3.13 to avoid known psycopg2 Unicode issues
    effective_url = DATABASE_URL
    try:
        if effective_url.startswith("postgresql://") and "+" not in effective_url:
            effective_url = effective_url.replace("postgresql://", "postgresql+psycopg://", 1)
    except Exception:
        effective_url = DATABASE_URL

    # Week 1, Day 3: Production-grade connection pool configuration
    # Optimized for high-concurrency workloads with automatic connection health checks
    
    # Pool size configuration (environment variables or defaults)
    pool_size = int(os.environ.get("DB_POOL_SIZE", "20"))  # Base pool size
    max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "40"))  # Additional connections under load
    pool_timeout = int(os.environ.get("DB_POOL_TIMEOUT", "30"))  # Wait time for connection (seconds)
    pool_recycle = int(os.environ.get("DB_POOL_RECYCLE", "3600"))  # Recycle connections after 1 hour
    
    # For Postgres, explicitly enforce UTF-8 client encoding to avoid Windows codepage pitfalls
    connect_args = {"options": "-c client_encoding=utf8"}
    
    try:
        from sqlalchemy.pool import QueuePool
        
        engine = create_engine(
            effective_url,
            poolclass=QueuePool,  # Week 1, Day 3: Explicit QueuePool (default, but explicit is better)
            pool_size=pool_size,  # Minimum pool size (always-open connections)
            max_overflow=max_overflow,  # Additional connections when pool exhausted
            pool_timeout=pool_timeout,  # Max wait time for connection from pool
            pool_recycle=pool_recycle,  # Recycle connections periodically (prevent stale connections)
            pool_pre_ping=True,  # Week 1, Day 3: CRITICAL - Test connection health before use
            echo=False,  # Set to True for SQL query debugging
            connect_args=connect_args,
            # Week 1, Day 3: Connection pool lifecycle logging
            pool_logging_name="db_pool"
        )
        
        logger.info(
            f"Database connection pool configured: "
            f"pool_size={pool_size}, max_overflow={max_overflow}, "
            f"total_max={pool_size + max_overflow}, pool_timeout={pool_timeout}s, "
            f"pool_recycle={pool_recycle}s, pool_pre_ping=True"
        )
        
    except TypeError:
        # Older SQLAlchemy may not accept all pool parameters; fallback
        logger.warning("Using fallback engine configuration (old SQLAlchemy version)")
        engine = create_engine(effective_url, pool_recycle=3600, connect_args=connect_args)

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


__all__ = ["engine", "SessionLocal", "Base", "get_db", "DATABASE_URL"]
