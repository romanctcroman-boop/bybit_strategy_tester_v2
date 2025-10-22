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
    # Prefer psycopg (psycopg3) driver on Windows/Python 3.13 to avoid known psycopg2 Unicode issues
    effective_url = DATABASE_URL
    try:
        if effective_url.startswith("postgresql://") and "+" not in effective_url:
            effective_url = effective_url.replace("postgresql://", "postgresql+psycopg://", 1)
    except Exception:
        effective_url = DATABASE_URL

    # For Postgres, explicitly enforce UTF-8 client encoding to avoid Windows codepage pitfalls
    connect_args = {"options": "-c client_encoding=utf8"}
    try:
        engine = create_engine(effective_url, pool_recycle=3600, connect_args=connect_args)
    except TypeError:
        # Older SQLAlchemy may not accept connect_args for non-DBAPI URLs; fallback
        engine = create_engine(effective_url, pool_recycle=3600)

# SessionLocal factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

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
