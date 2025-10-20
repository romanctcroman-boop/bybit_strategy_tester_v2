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
from typing import Generator, Optional
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import logging
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

# Read DATABASE_URL from environment; fallback to in-memory sqlite
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    logger.warning("DATABASE_URL not set; using in-memory sqlite for local imports/tests")
    DATABASE_URL = "sqlite:///:memory:"

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
