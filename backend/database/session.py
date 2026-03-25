"""
Database Session Management - Re-export Module

This module re-exports database session utilities from the main database module.
For new code, prefer importing directly from backend.database.

Note: This file exists for backward compatibility. The actual implementation
is in backend/database/__init__.py.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export from main database module to avoid breaking existing imports
from backend.database import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]


# Deprecated helper - use backend.database.get_db() directly
def get_session():
    """
    DEPRECATED: Use get_db() instead.

    This function exists for backward compatibility only.
    """
    logger.warning("get_session() is deprecated. Use get_db() from backend.database instead.")
    return get_db()
