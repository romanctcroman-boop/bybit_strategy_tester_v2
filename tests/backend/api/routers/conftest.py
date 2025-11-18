"""Fixtures for backend/api/routers tests"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.api.app import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def bypass_cache():
    """
    Bypass cache decorators for testing.
    Patches cache_manager to always return None (cache miss).
    This forces endpoints to execute fresh code instead of returning cached results.
    """
    # Mock get() to always return None (cache miss)
    # Mock set() to be a no-op
    with patch('backend.cache.cache_manager.CacheManager.get', return_value=None):
        with patch('backend.cache.cache_manager.CacheManager.set', return_value=None):
            with patch('backend.cache.cache_manager.CacheManager.delete', return_value=None):
                yield True


@pytest.fixture
def mock_data_service_class():
    """
    Mock DataService class that bypasses cache.
    Returns a mock class that can be used as context manager.
    """
    mock_instance = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    
    # Setup context manager behavior
    mock_instance.__enter__ = MagicMock(return_value=mock_instance)
    mock_instance.__exit__ = MagicMock(return_value=False)
    
    return mock_class, mock_instance
