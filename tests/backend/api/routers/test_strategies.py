"""
Comprehensive tests for backend/api/routers/strategies.py

Updated (2025-11-16):
    • Total tests: 26 (all passing)
    • Module statements (strategies.py): 104
    • Coverage (strategies.py): ~96.15% (4 uncovered lines: import fallback & guard branches)
    • Removed legacy cache decorators; using DI-based cache & data service dependencies
    • Validates dynamic config requirements per StrategyType enum

Test Coverage:
    - GET /strategies/ (list + filters + pagination + cache hit bypass)
    - GET /strategies/{id} (detail + 404 + cache hit + 501 no service)
    - POST /strategies/ (success, invalid type, missing required config, mean_reversion success, extra field rejection, 501)
    - PUT /strategies/{id} (success, not found, missing required config fields, 501)
    - DELETE /strategies/{id} (success, failed delete, 501)
    - Datetime serialization integrity
    - ImportError fallback path for _get_data_service()

Key Features Exercised:
    - Dependency injection overrides for cache & data service
    - Pattern-based cache invalidation assertions
    - Strategy schema validation (required keys per type)
    - Enum value serialization for stable external contract
"""

import fnmatch
from datetime import datetime, UTC
from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import strategies as strategies_module


VALID_SR_RSI_CONFIG = {'rsi_period': 14, 'overbought': 70, 'oversold': 30}


# ========================================================================
# FIXTURES AND MOCKS
# ========================================================================

@pytest.fixture
def mock_cache_manager():
    class MockCacheManager:
        def __init__(self):
            self.store = {}
            self.deleted_patterns: list[str] = []
            self.deleted_keys: list[str] = []

        async def get(self, key: str):
            return self.store.get(key)

        async def set(self, key: str, value, l1_ttl=None, l2_ttl=None):
            self.store[key] = value

        async def delete(self, key: str):
            self.deleted_keys.append(key)
            self.store.pop(key, None)

        async def delete_pattern(self, pattern: str):
            self.deleted_patterns.append(pattern)
            keys_to_delete = [k for k in list(self.store.keys()) if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                self.store.pop(key, None)
            return len(keys_to_delete)

    return MockCacheManager()


@pytest.fixture
def app(mock_data_service, mock_cache_manager):
    """Create FastAPI app with strategies router"""
    app = FastAPI()
    app.include_router(strategies_module.router, prefix="/strategies", tags=["strategies"])
    app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: mock_data_service
    app.dependency_overrides[strategies_module.get_cache_dependency] = lambda: mock_cache_manager
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)




@pytest.fixture
def mock_data_service():
    """Mock DataService for testing with context manager support"""
    
    # Mock strategy object
    class MockStrategy:
        def __init__(self, **kwargs):
            self.id = kwargs.get('id', 1)
            self.name = kwargs.get('name', 'Test Strategy')
            self.description = kwargs.get('description', 'A test trading strategy')
            self.strategy_type = kwargs.get('strategy_type', 'sr_rsi')  # ✅ Valid whitelist value
            self.config = kwargs.get('config', VALID_SR_RSI_CONFIG.copy())
            self.is_active = kwargs.get('is_active', True)
            self.created_at = kwargs.get('created_at', datetime(2023, 1, 1, tzinfo=UTC))
            self.updated_at = kwargs.get('updated_at', datetime(2023, 1, 1, tzinfo=UTC))
            
        @property
        def __dict__(self):
            return {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'strategy_type': self.strategy_type,
                'config': self.config,  # ✅ Changed from parameters
                'is_active': self.is_active,
                'created_at': self.created_at,
                'updated_at': self.updated_at,
            }
    
    # Create mock DataService instance with context manager support
    class MockDataServiceInstance:
        """Mock DataService instance that supports context manager protocol"""
        
        def __init__(self):
            self.MockStrategy = MockStrategy
            
            # Mock methods
            self.get_strategies = Mock(return_value=[
                MockStrategy(id=1, name='Strategy 1', is_active=True),
                MockStrategy(id=2, name='Strategy 2', is_active=False)
            ])
            self.count_strategies = Mock(return_value=2)
            self.get_strategy = Mock(return_value=MockStrategy(id=1, name='Test Strategy'))
            self.create_strategy = Mock(return_value=MockStrategy(id=1, name='New Strategy'))
            self.update_strategy = Mock(return_value=MockStrategy(id=1, name='Updated Strategy'))
            self.delete_strategy = Mock(return_value=True)
        
        def __enter__(self):
            """Enter context manager"""
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            """Exit context manager"""
            return False
    
    # Create callable class that returns MockDataServiceInstance
    class MockDataServiceClass:
        """Mock DataService class that can be called to create instances"""
        
        def __init__(self):
            self.instance = MockDataServiceInstance()
            # Expose mock class for test access
            self.MockStrategy = MockStrategy
            
            # Delegate all mock methods to instance for easier access in tests
            self.get_strategies = self.instance.get_strategies
            self.count_strategies = self.instance.count_strategies
            self.get_strategy = self.instance.get_strategy
            self.create_strategy = self.instance.create_strategy
            self.update_strategy = self.instance.update_strategy
            self.delete_strategy = self.instance.delete_strategy
        
        def __call__(self, *args, **kwargs):
            """Return the mock instance when called"""
            return self.instance
    
    return MockDataServiceClass()


# ========================================================================
# TEST: LIST STRATEGIES
# ========================================================================

class TestListStrategies:
    """Test GET /strategies/ endpoint"""
    
    def test_list_strategies_success(self, client, mock_data_service):
        """Test successful strategy list retrieval"""
        response = client.get("/strategies/")

        assert response.status_code == 200
        data = response.json()
        assert 'items' in data
        assert 'total' in data
        assert data['total'] == 2
        assert len(data['items']) == 2
    
    def test_list_strategies_with_is_active_filter(self, client, mock_data_service):
        """Test strategy list with is_active filter"""
        mock_data_service.instance.get_strategies.return_value = [
            mock_data_service.MockStrategy(id=1, is_active=True)
        ]
        mock_data_service.instance.count_strategies.return_value = 1
        
        response = client.get("/strategies/?is_active=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        # Verify filter was passed to DataService
        mock_data_service.instance.get_strategies.assert_called_once()
        call_kwargs = mock_data_service.instance.get_strategies.call_args[1]
        assert call_kwargs['is_active'] is True
    
    def test_list_strategies_with_strategy_type_filter(self, client, mock_data_service):
        """Test strategy list with strategy_type filter"""
        response = client.get("/strategies/?strategy_type=sr_rsi")  # ✅ Valid value
        
        assert response.status_code == 200
        call_kwargs = mock_data_service.instance.get_strategies.call_args[1]
        assert call_kwargs['strategy_type'] == 'sr_rsi'  # ✅ Changed
    
    def test_list_strategies_with_pagination(self, client, mock_data_service):
        """Test strategy list with pagination"""
        response = client.get("/strategies/?limit=10&offset=5")
        
        assert response.status_code == 200
        call_kwargs = mock_data_service.instance.get_strategies.call_args[1]
        assert call_kwargs['limit'] == 10
        assert call_kwargs['offset'] == 5

    def test_list_strategies_no_data_service(self, client):
        """Return empty list when data service isn't available"""
        client.app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: None

        response = client.get("/strategies/")

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    def test_list_strategies_uses_cache_when_available(self, client, mock_cache_manager, mock_data_service):
        """Ensure cache hit bypasses data service"""
        cache_key = strategies_module._build_list_cache_key(None, None, 100, 0)
        mock_cache_manager.store[cache_key] = {
            "items": [
                {
                    "id": 99,
                    "name": "Cached",
                    "description": "cached",
                    "strategy_type": "sr_rsi",
                    "config": VALID_SR_RSI_CONFIG.copy(),
                    "is_active": True,
                    "created_at": "2023-01-01T00:00:00+00:00",
                    "updated_at": "2023-01-01T00:00:00+00:00",
                }
            ],
            "total": 1,
        }

        response = client.get("/strategies/")

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["name"] == "Cached"
        mock_data_service.instance.get_strategies.assert_not_called()


# ========================================================================
# TEST: GET STRATEGY
# ========================================================================

class TestGetStrategy:
    """Test GET /strategies/{id} endpoint"""
    
    def test_get_strategy_success(self, client, mock_data_service):
        """Test successful strategy retrieval"""
        response = client.get("/strategies/1")

        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert 'name' in data
        assert data['name'] == 'Test Strategy'
    
    def test_get_strategy_not_found(self, client, mock_data_service):
        """Test get strategy when strategy doesn't exist"""
        mock_data_service.instance.get_strategy.return_value = None
        
        response = client.get("/strategies/999")
        
        assert response.status_code == 404

    def test_get_strategy_no_data_service(self, client):
        """Return 501 when backend isn't configured"""
        client.app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: None

        response = client.get("/strategies/1")

        assert response.status_code == 501

    def test_get_strategy_uses_cache(self, client, mock_cache_manager, mock_data_service):
        cache_key = strategies_module._build_detail_cache_key(1)
        mock_cache_manager.store[cache_key] = {
            "id": 1,
            "name": "Cached",
            "description": "cached",
            "strategy_type": "sr_rsi",
            "config": VALID_SR_RSI_CONFIG.copy(),
            "is_active": True,
            "created_at": "2023-01-01T00:00:00+00:00",
            "updated_at": "2023-01-01T00:00:00+00:00",
        }

        response = client.get("/strategies/1")

        assert response.status_code == 200
        assert response.json()["strategy_type"] == "sr_rsi"
        mock_data_service.instance.get_strategy.assert_not_called()


# ========================================================================
# TEST: CREATE STRATEGY
# ========================================================================

class TestCreateStrategy:
    """Test POST /strategies/ endpoint"""
    
    def test_create_strategy_success(self, client, mock_cache_manager):
        """Test successful strategy creation"""
        payload = {
            'name': 'New Strategy',
            'description': 'A new trading strategy',
            'strategy_type': 'sr_rsi',
            'config': VALID_SR_RSI_CONFIG.copy(),
            'is_active': True
        }
        
        response = client.post("/strategies/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert 'id' in data
        assert 'name' in data
        assert f"{strategies_module.LIST_CACHE_PREFIX}:*" in mock_cache_manager.deleted_patterns

    def test_create_strategy_invalid_strategy_type(self, client, mock_data_service):
        """Ensure whitelist validation rejects unsupported strategy_type values"""
        payload = {
            'name': 'Bad Strategy',
            'description': 'Invalid strategy type should fail',
            'strategy_type': 'not_supported',
            'config': VALID_SR_RSI_CONFIG.copy(),
            'is_active': True
        }

        response = client.post('/strategies/', json=payload)
        assert response.status_code == 422
        detail = response.json()
        assert any('Input should be' in str(err.get('msg', '')) for err in detail.get('detail', []))
        mock_data_service.instance.create_strategy.assert_not_called()

    def test_create_strategy_missing_required_config_fields(self, client, mock_data_service):
        payload = {
            'name': 'Mean Reversion Strategy',
            'description': 'Should fail due to missing config fields',
            'strategy_type': 'mean_reversion',
            'config': {},
            'is_active': True,
        }

        response = client.post('/strategies/', json=payload)

        assert response.status_code == 422
        detail = response.json()
        assert any('mean_reversion strategy requires config fields' in str(err.get('msg', '')) for err in detail.get('detail', []))
        mock_data_service.instance.create_strategy.assert_not_called()

    def test_create_strategy_mean_reversion_success(self, client, mock_cache_manager):
        payload = {
            'name': 'Mean Reversion Strategy',
            'description': 'Valid mean reversion config',
            'strategy_type': 'mean_reversion',
            'config': {
                'lookback_period': 20,
                'entry_threshold': 2.0,
                'exit_threshold': 0.5,
            },
            'is_active': True,
        }

        response = client.post('/strategies/', json=payload)

        assert response.status_code == 200
        assert f"{strategies_module.LIST_CACHE_PREFIX}:*" in mock_cache_manager.deleted_patterns

    def test_create_strategy_with_unsupported_field(self, client, mock_data_service):
        """Ensure extra fields like 'parameters' are explicitly rejected"""
        payload = {
            'name': 'Legacy Strategy',
            'description': 'Uses deprecated parameters field',
            'strategy_type': 'sr_rsi',
            'config': VALID_SR_RSI_CONFIG.copy(),
            'parameters': {'rsi_period': 14},
            'is_active': True
        }

        response = client.post('/strategies/', json=payload)

        assert response.status_code == 422
        detail = response.json()
        assert any('Extra inputs are not permitted' in str(err.get('msg', '')) for err in detail.get('detail', []))
        mock_data_service.instance.create_strategy.assert_not_called()
    
    def test_create_strategy_no_data_service(self, client):
        client.app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: None
        payload = {
            'name': 'New Strategy',
            'description': 'A new trading strategy',
            'strategy_type': 'sr_rsi',
            'config': VALID_SR_RSI_CONFIG.copy(),
            'is_active': True
        }

        response = client.post('/strategies/', json=payload)

        assert response.status_code == 501


# ========================================================================
# TEST: UPDATE STRATEGY
# ========================================================================

class TestUpdateStrategy:
    """Test PUT /strategies/{id} endpoint"""
    
    def test_update_strategy_success(self, client, mock_cache_manager):
        payload = {'name': 'Updated Strategy', 'is_active': False}

        response = client.put("/strategies/1", json=payload)

        assert response.status_code == 200
        assert f"{strategies_module.LIST_CACHE_PREFIX}:*" in mock_cache_manager.deleted_patterns
        assert strategies_module._build_detail_cache_key(1) in mock_cache_manager.deleted_keys
    
    def test_update_strategy_not_found(self, client, mock_data_service):
        mock_data_service.instance.update_strategy.return_value = None
        payload = {'name': 'Updated'}

        response = client.put("/strategies/999", json=payload)

        assert response.status_code == 404

    def test_update_strategy_missing_required_config_fields(self, client, mock_data_service):
        payload = {
            'strategy_type': 'mean_reversion',
            'config': {'lookback_period': 20, 'entry_threshold': 2.0},
        }

        response = client.put("/strategies/1", json=payload)

        assert response.status_code == 422
        detail = response.json()
        assert any('mean_reversion strategy requires config fields' in str(err.get('msg', '')) for err in detail.get('detail', []))
        mock_data_service.instance.update_strategy.assert_not_called()
    
    def test_update_strategy_no_data_service(self, client):
        payload = {'name': 'Updated'}
        client.app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: None

        response = client.put("/strategies/1", json=payload)

        assert response.status_code == 501


# ========================================================================
# TEST: DELETE STRATEGY
# ========================================================================

class TestDeleteStrategy:
    """Test DELETE /strategies/{id} endpoint"""
    
    def test_delete_strategy_success(self, client, mock_cache_manager):
        response = client.delete("/strategies/1")

        assert response.status_code == 200
        assert response.json()['success'] is True
        assert f"{strategies_module.LIST_CACHE_PREFIX}:*" in mock_cache_manager.deleted_patterns
        assert strategies_module._build_detail_cache_key(1) in mock_cache_manager.deleted_keys
    
    def test_delete_strategy_failed(self, client, mock_data_service, mock_cache_manager):
        mock_data_service.instance.delete_strategy.return_value = False

        response = client.delete("/strategies/999")

        assert response.status_code == 200
        assert response.json()['success'] is False
        assert strategies_module._build_detail_cache_key(999) in mock_cache_manager.deleted_keys
    
    def test_delete_strategy_no_data_service(self, client):
        client.app.dependency_overrides[strategies_module.get_data_service_dependency] = lambda: None

        response = client.delete("/strategies/1")

        assert response.status_code == 501


# ========================================================================
# TEST: DATETIME SERIALIZATION
# ========================================================================

class TestDatetimeSerialization:
    """Test datetime field serialization in responses"""
    
    def test_list_strategies_datetime_serialization(self, client, mock_data_service):
        """Test that datetime fields are serialized to ISO format in list"""
        response = client.get("/strategies/")
        
        assert response.status_code == 200
        data = response.json()
        for item in data['items']:
            assert 'created_at' in item
            assert 'updated_at' in item
            assert isinstance(item['created_at'], str)
            assert isinstance(item['updated_at'], str)
            datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
    
    def test_get_strategy_datetime_serialization(self, client, mock_data_service):
        """Test that datetime fields are serialized to ISO format in detail"""
        response = client.get("/strategies/1")
        
        assert response.status_code == 200
        data = response.json()
        assert 'created_at' in data
        assert 'updated_at' in data
        datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))


# ========================================================================
# TEST: MODULE IMPORT ERROR HANDLING
# ========================================================================

class TestModuleImportErrorHandling:
    """Test module-level ImportError handling for DataService"""
    
    def test_get_data_service_exception_handling(self):
        """Test that _get_data_service catches exceptions and returns None (lines 10-15)"""
        from backend.api.routers import strategies
        
        # Temporarily replace the import to trigger exception
        import sys
        import builtins
        
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if 'data_service' in name:
                raise ImportError("Simulated import error")
            return original_import(name, *args, **kwargs)
        
        # Mock the import and call _get_data_service
        with patch('builtins.__import__', side_effect=mock_import):
            result = strategies._get_data_service()
            # Function should catch Exception and return None (lines 10-15)
            assert result is None
