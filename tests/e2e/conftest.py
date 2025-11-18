"""
E2E Test Configuration and Fixtures

Provides test fixtures for end-to-end integration tests.

Note: These tests use the REAL application instance via TestClient.
For database isolation, they use app.dependency_overrides to inject test database sessions.
"""

import pytest
import os
import sys

from backend.database import Base, get_db


# Test database URL (use separate test database)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite:///test_e2e.db"  # Use SQLite for E2E tests by default
)


# Pytest configuration
def pytest_configure(config):
    """Configure custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )


# Environment check (non-blocking for now)
@pytest.fixture(scope="session", autouse=True)
def check_test_environment():
    """
    Check that test environment is properly configured.
    
    Note: This is a lightweight check that prints warnings but doesn't fail.
    For production E2E tests, you should enable strict checking.
    """
    warnings = []
    
    # Check Python version
    if sys.version_info < (3, 13):
        warnings.append(f"Python {sys.version_info.major}.{sys.version_info.minor} detected (recommend 3.13+)")
    
    # Check TEST_DATABASE_URL
    if TEST_DATABASE_URL.startswith("sqlite"):
        warnings.append("Using SQLite for E2E tests (recommend PostgreSQL for production)")
    
    if warnings:
        print("\n⚠️  E2E Test Environment Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
    else:
        print("\n✅ E2E Test environment check passed")
    
    print(f"   Database: {TEST_DATABASE_URL}")
    
    yield
    
    # Cleanup: Remove SQLite test database
    if TEST_DATABASE_URL.startswith("sqlite:///"):
        db_file = TEST_DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                print(f"\n🗑️  Removed test database: {db_file}")
            except Exception as e:
                print(f"\n⚠️  Could not remove test database: {e}")


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine"""
    from sqlalchemy import create_engine
    
    # Set TEST_DATABASE_URL in environment for application to use
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    else:
        engine = create_engine(TEST_DATABASE_URL)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Drop all tables after tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """
    Create a new database session for each test.
    Uses transactions with rollback for isolation.
    """
    from sqlalchemy.orm import sessionmaker, Session
    from backend.api.app import app
    
    connection = test_engine.connect()
    transaction = connection.begin()
    
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestSessionLocal()
    
    # Override the get_db dependency
    def override_get_db():
        try:
            yield session
        finally:
            pass  # Don't close here, we'll do it in teardown
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    # Rollback transaction and close
    session.close()
    transaction.rollback()
    connection.close()
    
    # Clear dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def clean_database(test_db):
    """
    Ensure database is clean before each test.
    Deletes all records from all tables.
    """
    # Import models
    from backend.models import (
        Strategy, Backtest, Optimization
    )
    
    # For optional models
    try:
        from backend.models import Trade
    except ImportError:
        Trade = None
    
    try:
        from backend.models import Template
    except ImportError:
        Template = None
    
    # Delete all records (in correct order to avoid FK constraints)
    if Trade is not None:
        try:
            test_db.query(Trade).delete()
        except Exception:
            pass
    
    try:
        test_db.query(Backtest).delete()
    except Exception:
        pass
    
    try:
        test_db.query(Optimization).delete()
    except Exception:
        pass
    
    try:
        test_db.query(Strategy).delete()
    except Exception:
        pass
    
    if Template is not None:
        try:
            test_db.query(Template).delete()
        except Exception:
            pass
    
    test_db.commit()
    
    yield test_db


@pytest.fixture(scope="function")
def sample_strategy_code():
    """Sample strategy code for testing"""
    return """
from backend.strategies.base import BaseStrategy
import pandas as pd

class SampleStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.sma_short = 10
        self.sma_long = 30
    
    def calculate_indicators(self, df):
        df['sma_short'] = df['close'].rolling(window=self.sma_short).mean()
        df['sma_long'] = df['close'].rolling(window=self.sma_long).mean()
        return df
    
    def generate_signals(self, df):
        df['signal'] = 0
        df.loc[df['sma_short'] > df['sma_long'], 'signal'] = 1
        df.loc[df['sma_short'] < df['sma_long'], 'signal'] = -1
        return df
"""


@pytest.fixture(scope="function")
def sample_strategy_params():
    """Sample strategy parameters"""
    return {
        "sma_short": {
            "type": "int",
            "default": 10,
            "min": 5,
            "max": 20
        },
        "sma_long": {
            "type": "int",
            "default": 30,
            "min": 20,
            "max": 50
        }
    }

