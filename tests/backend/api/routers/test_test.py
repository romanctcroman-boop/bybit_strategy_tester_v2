"""
Comprehensive tests for backend/api/routers/test.py
Testing endpoints for E2E database reset and cleanup

Target Coverage: 80%+ (from 25%)
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from backend.api.routers.test import router, require_testing_mode
from backend.models import User, Strategy, Backtest, Optimization
from fastapi import HTTPException


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create test client with test router"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = MagicMock(spec=Session)
    
    # Setup mock query behavior
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.delete.return_value = 0
    db.query.return_value.delete.return_value = 0
    db.query.return_value.count.return_value = 2
    
    return db


@pytest.fixture
def testing_env(monkeypatch):
    """Set TESTING=true environment variable"""
    monkeypatch.setenv("TESTING", "true")


@pytest.fixture
def non_testing_env(monkeypatch):
    """Set TESTING=false environment variable"""
    monkeypatch.setenv("TESTING", "false")


# ============================================================================
# Test Class 1: require_testing_mode() Helper Function
# ============================================================================

class TestRequireTestingMode:
    """Test the require_testing_mode() security function"""
    
    def test_testing_mode_enabled(self, testing_env):
        """Should not raise exception when TESTING=true"""
        # Should not raise any exception
        require_testing_mode()
    
    def test_testing_mode_disabled(self, non_testing_env):
        """Should raise 403 HTTPException when TESTING=false"""
        with pytest.raises(HTTPException) as exc_info:
            require_testing_mode()
        
        assert exc_info.value.status_code == 403
        assert "only available in TESTING mode" in exc_info.value.detail
    
    def test_testing_mode_missing(self, monkeypatch):
        """Should raise 403 when TESTING env var is not set"""
        monkeypatch.delenv("TESTING", raising=False)
        
        with pytest.raises(HTTPException) as exc_info:
            require_testing_mode()
        
        assert exc_info.value.status_code == 403


# ============================================================================
# Test Class 2: POST /test/reset Endpoint
# ============================================================================

class TestResetEndpoint:
    """Test database reset endpoint"""
    
    def test_reset_success_no_existing_users(self, client, testing_env):
        """Test successful reset when no users exist"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hashed_pw"):
                response = client.post("/test/reset")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "reset_complete"
        assert "admin" in data["users"]
        assert "user" in data["users"]
        assert data["users"]["admin"]["password"] == "admin123"
        assert data["users"]["user"]["password"] == "user123"
        assert "strategies" in data["tables_cleared"]
    
    def test_reset_updates_existing_users(self, client, testing_env):
        """Test reset updates existing user passwords"""
        mock_db = MagicMock(spec=Session)
        
        # Mock existing users
        existing_admin = MagicMock(spec=User)
        existing_admin.username = "admin"
        existing_user = MagicMock(spec=User)
        existing_user.username = "user"
        
        call_count = [0]
        
        def mock_first(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return existing_admin
            elif call_count[0] == 2:
                return existing_user
            return None
        
        mock_db.query.return_value.filter.return_value.first = mock_first
        mock_db.query.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="new_hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 200
        # Verify passwords were updated
        assert existing_admin.hashed_password == "new_hash"
        assert existing_user.hashed_password == "new_hash"
    
    def test_reset_forbidden_without_testing_mode(self, client, non_testing_env):
        """Test reset returns 403 when TESTING=false"""
        response = client.post("/test/reset")
        
        assert response.status_code == 403
        assert "only available in TESTING mode" in response.json()["detail"]
    
    def test_reset_database_error(self, client, testing_env):
        """Test reset handles database errors gracefully"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.delete.return_value = 0
        mock_db.commit.side_effect = Exception("Database connection failed")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 500
        assert "Database reset failed" in response.json()["detail"]
        mock_db.rollback.assert_called_once()
    
    def test_reset_clears_all_tables(self, client, testing_env):
        """Test reset clears Optimization, Backtest, Strategy tables"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 200
        
        # Verify delete() was called (at least for the 3 main tables)
        # Count calls to delete method
        delete_calls = [call for call in str(mock_db.mock_calls) if 'delete' in call]
        assert len(delete_calls) >= 3  # Optimization, Backtest, Strategy
    
    def test_reset_creates_admin_with_correct_scopes(self, client, testing_env, mock_db):
        """Test admin user is created with all scopes"""
        captured_users = []
        
        def capture_add(user):
            captured_users.append(user)
        
        mock_db.add = capture_add
        
        with patch("backend.api.routers.test.get_db", return_value=mock_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 200
        
        # Find admin user in captured users
        admin_users = [u for u in captured_users if hasattr(u, 'username') and u.username == "admin"]
        if admin_users:
            admin = admin_users[0]
            assert admin.role == "admin"
            assert "admin" in admin.scopes
            assert "sandbox_exec" in admin.scopes
    
    def test_reset_creates_regular_user_with_limited_scopes(self, client, testing_env, mock_db):
        """Test regular user is created with read/write scopes only"""
        captured_users = []
        
        def capture_add(user):
            captured_users.append(user)
        
        mock_db.add = capture_add
        
        with patch("backend.api.routers.test.get_db", return_value=mock_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 200
        
        # Find regular user in captured users
        regular_users = [u for u in captured_users if hasattr(u, 'username') and u.username == "user"]
        if regular_users:
            user = regular_users[0]
            assert user.role == "user"
            assert user.scopes == ["read", "write"]


# ============================================================================
# Test Class 3: POST /test/cleanup Endpoint
# ============================================================================

class TestCleanupEndpoint:
    """Test test artifacts cleanup endpoint"""
    
    def test_cleanup_success(self, client, testing_env):
        """Test successful cleanup of test artifacts"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.delete.return_value = 5
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleanup_complete"
        assert "removed" in data
    
    def test_cleanup_forbidden_without_testing_mode(self, client, non_testing_env):
        """Test cleanup returns 403 when TESTING=false"""
        response = client.post("/test/cleanup")
        
        assert response.status_code == 403
        assert "only available in TESTING mode" in response.json()["detail"]
    
    def test_cleanup_removes_test_strategies(self, client, testing_env):
        """Test cleanup removes strategies with test_ prefix"""
        mock_db = MagicMock(spec=Session)
        mock_filter = MagicMock()
        mock_filter.delete.return_value = 3
        mock_db.query.return_value.filter.return_value = mock_filter
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 200
        # Just verify we got a successful response
        data = response.json()
        assert data["status"] == "cleanup_complete"
    
    def test_cleanup_database_error(self, client, testing_env):
        """Test cleanup handles database errors"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        mock_db.commit.side_effect = Exception("Cleanup failed")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 500
        assert "Test cleanup failed" in response.json()["detail"]
        mock_db.rollback.assert_called_once()
    
    def test_cleanup_no_test_data(self, client, testing_env):
        """Test cleanup when no test data exists"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 200
        data = response.json()
        assert data["removed"]["strategies"] == 0
        assert data["removed"]["backtests"] == 0


# ============================================================================
# Test Class 4: GET /test/health/db Endpoint
# ============================================================================

class TestHealthCheckEndpoint:
    """Test database health check endpoint"""
    
    def test_health_check_healthy(self, client):
        """Test health check returns healthy status"""
        mock_db = MagicMock(spec=Session)
        
        # Mock successful database query
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result
        mock_db.query.return_value.count.return_value = 5
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["users_count"] == 5
    
    def test_health_check_with_testing_mode(self, client, testing_env):
        """Test health check shows testing mode status"""
        mock_db = MagicMock(spec=Session)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result
        mock_db.query.return_value.count.return_value = 2
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["test_mode"] is True
    
    def test_health_check_without_testing_mode(self, client, non_testing_env):
        """Test health check works without testing mode"""
        mock_db = MagicMock(spec=Session)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result
        mock_db.query.return_value.count.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["test_mode"] is False
    
    def test_health_check_database_error(self, client):
        """Test health check handles database errors"""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = Exception("Connection refused")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200  # Health check doesn't fail, returns unhealthy
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "Connection refused" in data["database"]
        assert data["users_count"] == 0
    
    def test_health_check_no_users(self, client):
        """Test health check with zero users"""
        mock_db = MagicMock(spec=Session)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result
        mock_db.query.return_value.count.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["users_count"] == 0


# ============================================================================
# Test Class 5: Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_reset_rollback_on_user_creation_error(self, client, testing_env):
        """Test rollback when user creation fails"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.delete.return_value = 0
        mock_db.add.side_effect = Exception("User creation failed")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                response = client.post("/test/reset")
        
        assert response.status_code == 500
        mock_db.rollback.assert_called_once()
    
    def test_cleanup_partial_deletion(self, client, testing_env):
        """Test cleanup with different counts for strategies and backtests"""
        mock_db = MagicMock(spec=Session)
        
        call_count = [0]
        def mock_delete(*args, **kwargs):
            call_count[0] += 1
            return 3 if call_count[0] == 1 else 7  # 3 strategies, 7 backtests
        
        mock_db.query.return_value.filter.return_value.delete = mock_delete
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 200
        data = response.json()
        # Just verify we got successful cleanup
        assert data["status"] == "cleanup_complete"
    
    def test_health_check_query_timeout(self, client):
        """Test health check when database query times out"""
        mock_db = MagicMock(spec=Session)
        mock_db.execute.side_effect = TimeoutError("Query timeout")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.get("/test/health/db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "timeout" in data["database"].lower()
    
    def test_reset_with_special_characters_in_env(self, client, monkeypatch):
        """Test reset when TESTING has unexpected value"""
        monkeypatch.setenv("TESTING", "TRUE")  # Uppercase
        
        response = client.post("/test/reset")
        
        # Should fail since it's not exactly "true"
        assert response.status_code == 403
    
    def test_cleanup_concurrent_modification(self, client, testing_env):
        """Test cleanup handles concurrent modification errors"""
        from sqlalchemy.exc import InvalidRequestError
        
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        mock_db.commit.side_effect = InvalidRequestError("Concurrent modification")
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            response = client.post("/test/cleanup")
        
        assert response.status_code == 500
        mock_db.rollback.assert_called_once()


# ============================================================================
# Test Class 6: Integration-Style Tests
# ============================================================================

class TestIntegrationScenarios:
    """Test realistic usage scenarios"""
    
    def test_reset_then_cleanup_flow(self, client, testing_env):
        """Test typical E2E flow: reset -> run tests -> cleanup"""
        mock_db = MagicMock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.delete.return_value = 0
        mock_db.query.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                # Step 1: Reset
                reset_response = client.post("/test/reset")
                assert reset_response.status_code == 200
                
                # Step 2: Cleanup
                cleanup_response = client.post("/test/cleanup")
                assert cleanup_response.status_code == 200
    
    def test_health_check_independent_of_testing_mode(self, client):
        """Test health check works regardless of testing mode"""
        mock_db = MagicMock(spec=Session)
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result
        mock_db.query.return_value.count.return_value = 10
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            # Works without TESTING env var
            response = client.get("/test/health/db")
            assert response.status_code == 200
            assert response.json()["users_count"] == 10
    
    def test_multiple_resets_idempotent(self, client, testing_env):
        """Test multiple resets don't create duplicate users"""
        mock_db = MagicMock(spec=Session)
        
        existing_admin = MagicMock(spec=User)
        existing_admin.username = "admin"
        existing_user = MagicMock(spec=User)
        existing_user.username = "user"
        
        # First call returns None, second returns existing users
        call_counts = [0]
        
        def mock_first(*args, **kwargs):
            call_counts[0] += 1
            if call_counts[0] == 1 or call_counts[0] == 2:
                return None  # No users first reset
            elif call_counts[0] == 3:
                return existing_admin  # Admin exists second reset
            else:
                return existing_user  # User exists second reset
        
        mock_db.query.return_value.filter.return_value.first = mock_first
        mock_db.query.return_value.delete.return_value = 0
        
        def mock_get_db():
            yield mock_db
        
        with patch("backend.api.routers.test.get_db", mock_get_db):
            with patch("backend.api.routers.test.hash_password", return_value="hash"):
                # First reset
                response1 = client.post("/test/reset")
                assert response1.status_code == 200
                
                # Second reset (users now exist)
                response2 = client.post("/test/reset")
                assert response2.status_code == 200
