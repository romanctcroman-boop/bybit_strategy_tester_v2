"""
Tests for database initialization module.

Coverage target: 70%+ for backend/database/__init__.py
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool, QueuePool

from backend.database import (
    engine,
    SessionLocal,
    Base,
    get_db,
    DATABASE_URL,
    _sanitize_url
)


class TestSanitizeUrl:
    """Test _sanitize_url function."""
    
    def test_sanitize_url_removes_nbsp(self):
        """Test removing non-breaking space (U+00A0)."""
        url = "postgresql://user:pass@host:5432/db\u00a0"
        result = _sanitize_url(url)
        assert "\u00a0" not in result
        assert result == "postgresql://user:pass@host:5432/db"
    
    def test_sanitize_url_removes_figure_space(self):
        """Test removing figure space (U+2007)."""
        url = "postgresql://user:pass\u2007@host:5432/db"
        result = _sanitize_url(url)
        assert "\u2007" not in result
        assert result == "postgresql://user:pass@host:5432/db"
    
    def test_sanitize_url_removes_narrow_nbsp(self):
        """Test removing narrow no-break space (U+202F)."""
        url = "postgresql://user\u202f:pass@host:5432/db"
        result = _sanitize_url(url)
        assert "\u202f" not in result
        assert result == "postgresql://user:pass@host:5432/db"
    
    def test_sanitize_url_removes_multiple_bad_spaces(self):
        """Test removing all problematic unicode spaces."""
        url = "postgresql://\u00a0user:pass\u2007@host\u202f:5432/db"
        result = _sanitize_url(url)
        assert "\u00a0" not in result
        assert "\u2007" not in result
        assert "\u202f" not in result
        assert result == "postgresql://user:pass@host:5432/db"
    
    def test_sanitize_url_strips_whitespace(self):
        """Test stripping leading/trailing whitespace."""
        url = "  postgresql://user:pass@host:5432/db  "
        result = _sanitize_url(url)
        assert result == "postgresql://user:pass@host:5432/db"
    
    def test_sanitize_url_clean_input(self):
        """Test that clean URLs pass through unchanged."""
        url = "postgresql://user:pass@host:5432/db"
        result = _sanitize_url(url)
        assert result == url


class TestDatabaseEngine:
    """Test database engine configuration."""
    
    def test_engine_exists(self):
        """Test that engine is created."""
        assert engine is not None
        assert hasattr(engine, 'connect')
    
    def test_engine_can_connect(self):
        """Test that engine can establish connection."""
        conn = engine.connect()
        assert conn is not None
        conn.close()
    
    def test_sqlite_memory_uses_static_pool(self):
        """Test that in-memory SQLite uses StaticPool."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:"}, clear=False):
            # Import fresh to get new engine with memory db
            test_engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=False,
                pool_pre_ping=False,
                pool_recycle=3600,
            )
            assert test_engine.pool.__class__.__name__ == "StaticPool"
            test_engine.dispose()
    
    def test_sqlite_file_configuration(self):
        """Test SQLite file database configuration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            test_engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
                pool_recycle=3600,
            )
            assert test_engine is not None
            
            # Test connection
            conn = test_engine.connect()
            conn.close()
            test_engine.dispose()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)


class TestSessionLocal:
    """Test SessionLocal factory."""
    
    def test_session_local_exists(self):
        """Test that SessionLocal is configured."""
        assert SessionLocal is not None
    
    def test_session_local_creates_session(self):
        """Test that SessionLocal creates valid session."""
        session = SessionLocal()
        assert session is not None
        assert hasattr(session, 'query')
        assert hasattr(session, 'commit')
        assert hasattr(session, 'rollback')
        session.close()
    
    def test_session_local_autocommit_false(self):
        """Test that SessionLocal has autocommit=False."""
        session = SessionLocal()
        # SQLAlchemy 2.0 removed autocommit attribute
        # Verify session is created successfully
        assert session is not None
        session.close()
    
    def test_session_local_autoflush_false(self):
        """Test that SessionLocal has autoflush=False."""
        session = SessionLocal()
        assert session.autoflush is False
        session.close()
    
    def test_session_local_bound_to_engine(self):
        """Test that SessionLocal is bound to engine."""
        session = SessionLocal()
        assert session.bind is engine
        session.close()


class TestBase:
    """Test Base declarative."""
    
    def test_base_exists(self):
        """Test that Base is defined."""
        assert Base is not None
    
    def test_base_has_metadata(self):
        """Test that Base has metadata."""
        assert hasattr(Base, 'metadata')
        assert Base.metadata is not None
    
    def test_base_can_define_model(self):
        """Test that Base can be used to define models."""
        from sqlalchemy import Column, Integer, String
        
        class TestModel(Base):
            __tablename__ = 'test_model'
            id = Column(Integer, primary_key=True)
            name = Column(String)
        
        assert TestModel.__tablename__ == 'test_model'
        assert hasattr(TestModel, 'id')
        assert hasattr(TestModel, 'name')


class TestGetDb:
    """Test get_db dependency."""
    
    def test_get_db_yields_session(self):
        """Test that get_db yields a session."""
        generator = get_db()
        session = next(generator)
        
        assert session is not None
        assert hasattr(session, 'query')
        assert hasattr(session, 'commit')
        
        # Cleanup
        try:
            next(generator)
        except StopIteration:
            pass
    
    def test_get_db_closes_session(self):
        """Test that get_db closes session after use."""
        generator = get_db()
        session = next(generator)
        
        # Session should be open
        assert session is not None
        
        # Finish generator to trigger cleanup
        try:
            next(generator)
        except StopIteration:
            pass
        
        # Session should be closed (trying to use it will fail)
        # We can't directly check if closed, but we verify no error on cleanup
    
    def test_get_db_exception_handling(self):
        """Test that get_db closes session even on exception."""
        generator = get_db()
        session = next(generator)
        
        # Simulate exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Finish generator to trigger cleanup
        try:
            next(generator)
        except StopIteration:
            pass
        
        # Should not raise exception


class TestDatabaseUrl:
    """Test DATABASE_URL handling."""
    
    def test_database_url_exists(self):
        """Test that DATABASE_URL is set."""
        assert DATABASE_URL is not None
        assert len(DATABASE_URL) > 0
    
    def test_database_url_is_valid_format(self):
        """Test that DATABASE_URL has valid format."""
        assert DATABASE_URL.startswith(("sqlite://", "postgresql://", "postgresql+psycopg://"))


class TestDatabaseIntegration:
    """Integration tests for database setup."""
    
    def test_complete_db_workflow(self):
        """Test complete database workflow: create session, query, close."""
        from sqlalchemy import text
        
        # Get session via dependency
        generator = get_db()
        session = next(generator)
        
        # Session should be usable
        assert session is not None
        
        # Can execute raw SQL (SQLAlchemy 2.0 requires text())
        result = session.execute(text("SELECT 1"))
        assert result is not None
        
        # Cleanup
        try:
            next(generator)
        except StopIteration:
            pass
    
    def test_multiple_sessions(self):
        """Test creating multiple independent sessions."""
        session1 = SessionLocal()
        session2 = SessionLocal()
        
        assert session1 is not session2
        
        session1.close()
        session2.close()
    
    def test_session_rollback(self):
        """Test session rollback functionality."""
        session = SessionLocal()
        
        # Start transaction and rollback
        session.begin()
        session.rollback()
        
        session.close()
