"""
E2E Error Handling Tests

Tests error scenarios and edge cases across the entire system.

Test categories:
- Invalid input validation (400, 422)
- Resource not found (404)
- Constraint violations (409)
- Rate limiting and throttling
- External API failures
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from backend.api.app import app


@pytest.fixture(scope="module")
def client():
    """Create test client"""
    return TestClient(app)


class TestStrategyValidation:
    """Test strategy creation validation errors"""
    
    def test_create_strategy_invalid_code(self, client):
        """Test strategy with syntax error in code"""
        strategy_data = {
            "name": "Invalid Strategy",
            "description": "Has syntax error",
            "code": "def broken_function(\n    print('missing closing parenthesis'",
            "parameters": {}
        }
        
        response = client.post("/api/v1/strategies", json=strategy_data)
        
        assert response.status_code == 422
        error = response.json()
        assert "detail" in error
        print(f"\n✅ Caught syntax error: {error['detail']}")
    
    def test_create_strategy_missing_required_fields(self, client):
        """Test strategy missing required fields"""
        strategy_data = {
            "name": "Incomplete Strategy"
            # Missing code and parameters
        }
        
        response = client.post("/api/v1/strategies", json=strategy_data)
        
        assert response.status_code == 422
        error = response.json()
        assert "detail" in error
        print(f"\n✅ Caught missing fields: {error['detail']}")
    
    def test_create_strategy_invalid_parameter_type(self, client):
        """Test strategy with invalid parameter type"""
        strategy_data = {
            "name": "Bad Parameters",
            "code": "class Test(Strategy): pass",
            "parameters": {
                "period": {
                    "type": "invalid_type",  # Invalid type
                    "default": 20
                }
            }
        }
        
        response = client.post("/api/v1/strategies", json=strategy_data)
        
        assert response.status_code == 422
        print(f"\n✅ Caught invalid parameter type")
    
    def test_create_duplicate_strategy_name(self, client):
        """Test creating strategy with duplicate name"""
        strategy_data = {
            "name": "Duplicate Test Strategy",
            "description": "First strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        
        # Create first strategy
        response1 = client.post("/api/v1/strategies", json=strategy_data)
        assert response1.status_code == 201
        strategy_id = response1.json()["id"]
        
        # Try to create duplicate
        response2 = client.post("/api/v1/strategies", json=strategy_data)
        
        # Should return 409 Conflict or 422 Validation Error
        assert response2.status_code in [409, 422]
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught duplicate strategy name")


class TestBacktestValidation:
    """Test backtest validation errors"""
    
    def test_backtest_nonexistent_strategy(self, client):
        """Test backtest with strategy that doesn't exist"""
        backtest_data = {
            "strategy_id": "00000000-0000-0000-0000-000000000000",  # Invalid UUID
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        
        assert response.status_code == 404
        error = response.json()
        assert "not found" in error["detail"].lower()
        print(f"\n✅ Caught nonexistent strategy error")
    
    def test_backtest_invalid_date_range(self, client):
        """Test backtest with end_date before start_date"""
        # First create a valid strategy
        strategy_data = {
            "name": "Date Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        assert response.status_code == 201
        strategy_id = response.json()["id"]
        
        # Create backtest with invalid dates
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() - timedelta(days=30)).isoformat(),  # Before start
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        
        assert response.status_code == 422
        error = response.json()
        assert "date" in str(error["detail"]).lower()
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught invalid date range error")
    
    def test_backtest_invalid_symbol(self, client):
        """Test backtest with invalid trading symbol"""
        # Create strategy
        strategy_data = {
            "name": "Symbol Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create backtest with invalid symbol
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "INVALID123",  # Invalid symbol
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        
        # Should fail during execution or validation
        assert response.status_code in [400, 422]
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught invalid symbol error")
    
    def test_backtest_zero_capital(self, client):
        """Test backtest with zero or negative initial capital"""
        # Create strategy
        strategy_data = {
            "name": "Capital Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Test zero capital
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 0.0  # Invalid
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        assert response.status_code == 422
        
        # Test negative capital
        backtest_data["initial_capital"] = -1000.0
        response = client.post("/api/v1/backtests", json=backtest_data)
        assert response.status_code == 422
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught invalid capital errors")


class TestOptimizationValidation:
    """Test optimization validation errors"""
    
    def test_optimization_empty_param_ranges(self, client):
        """Test optimization with empty parameter ranges"""
        # Create strategy
        strategy_data = {
            "name": "Opt Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {"period": {"type": "int", "default": 20}}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create optimization with empty ranges
        opt_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "optimization_type": "grid",
            "param_ranges": {},  # Empty
            "metric": "sharpe_ratio"
        }
        
        response = client.post("/api/v1/optimizations", json=opt_data)
        assert response.status_code == 422
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught empty param ranges error")
    
    def test_optimization_invalid_metric(self, client):
        """Test optimization with invalid metric"""
        # Create strategy
        strategy_data = {
            "name": "Metric Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {"period": {"type": "int", "default": 20}}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create optimization with invalid metric
        opt_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "optimization_type": "grid",
            "param_ranges": {"period": [10, 20, 30]},
            "metric": "invalid_metric"  # Invalid
        }
        
        response = client.post("/api/v1/optimizations", json=opt_data)
        assert response.status_code == 422
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Caught invalid metric error")


class TestResourceNotFound:
    """Test 404 Not Found scenarios"""
    
    def test_get_nonexistent_strategy(self, client):
        """Test getting strategy that doesn't exist"""
        response = client.get("/api/v1/strategies/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        print(f"\n✅ 404: Strategy not found")
    
    def test_get_nonexistent_backtest(self, client):
        """Test getting backtest that doesn't exist"""
        response = client.get("/api/v1/backtests/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        print(f"\n✅ 404: Backtest not found")
    
    def test_export_nonexistent_backtest(self, client):
        """Test exporting CSV for nonexistent backtest"""
        response = client.get("/api/v1/export/backtests/00000000-0000-0000-0000-000000000000/csv")
        assert response.status_code == 404
        print(f"\n✅ 404: Backtest export not found")
    
    def test_delete_nonexistent_strategy(self, client):
        """Test deleting strategy that doesn't exist"""
        response = client.delete("/api/v1/strategies/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        print(f"\n✅ 404: Strategy delete not found")


class TestBoundaryConditions:
    """Test boundary conditions and edge cases"""
    
    def test_backtest_minimum_date_range(self, client):
        """Test backtest with 1-day date range"""
        # Create strategy
        strategy_data = {
            "name": "Boundary Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create backtest with 1-day range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        
        # Should either succeed or fail with validation error (not 500)
        assert response.status_code in [201, 400, 422]
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Handled minimum date range")
    
    def test_strategy_with_very_long_code(self, client):
        """Test strategy with very long code (stress test)"""
        long_code = "class Test(Strategy):\n" + "    pass\n" * 1000
        
        strategy_data = {
            "name": "Long Code Strategy",
            "code": long_code,
            "parameters": {}
        }
        
        response = client.post("/api/v1/strategies", json=strategy_data)
        
        # Should handle gracefully (may succeed or fail with size limit)
        assert response.status_code in [201, 413, 422]
        
        if response.status_code == 201:
            strategy_id = response.json()["id"]
            client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Handled very long code")


class TestConcurrency:
    """Test concurrent operations and race conditions"""
    
    def test_concurrent_backtest_creation(self, client):
        """Test creating multiple backtests simultaneously"""
        import threading
        
        # Create strategy
        strategy_data = {
            "name": "Concurrent Test Strategy",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create multiple backtests concurrently
        results = []
        
        def create_backtest(symbol):
            backtest_data = {
                "strategy_id": strategy_id,
                "symbol": symbol,
                "timeframe": "1h",
                "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
                "end_date": datetime.now().isoformat(),
                "initial_capital": 10000.0
            }
            response = client.post("/api/v1/backtests", json=backtest_data)
            results.append(response.status_code)
        
        threads = []
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        
        for symbol in symbols:
            thread = threading.Thread(target=create_backtest, args=(symbol,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert all(status == 201 for status in results)
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Handled concurrent backtest creation")
        print(f"   Created {len(results)} backtests simultaneously")


@pytest.mark.integration
class TestExternalAPIDependencies:
    """Test behavior when external APIs fail"""
    
    def test_backtest_with_data_fetch_failure(self, client):
        """
        Test backtest behavior when Bybit API fails.
        
        Note: This requires mocking or using invalid configuration
        to trigger data fetch failures.
        """
        # Create strategy
        strategy_data = {
            "name": "Data Fetch Test",
            "code": "class Test(Strategy): pass",
            "parameters": {}
        }
        response = client.post("/api/v1/strategies", json=strategy_data)
        strategy_id = response.json()["id"]
        
        # Create backtest with very old dates (likely to fail data fetch)
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2010-01-01T00:00:00",  # Bitcoin didn't exist
            "end_date": "2010-01-02T00:00:00",
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        
        # Should handle gracefully
        assert response.status_code in [201, 400, 422]
        
        # Cleanup
        client.delete(f"/api/v1/strategies/{strategy_id}")
        
        print(f"\n✅ Handled potential data fetch failure gracefully")


class TestAuthenticationErrors:
    """Test authentication and authorization errors (if implemented)"""
    
    @pytest.mark.skip(reason="Auth not yet implemented")
    def test_unauthorized_access(self, client):
        """Test accessing protected endpoints without authentication"""
        response = client.get("/api/v1/strategies")
        # Should return 401 Unauthorized if auth is enabled
        assert response.status_code in [200, 401]
    
    @pytest.mark.skip(reason="Auth not yet implemented")
    def test_forbidden_access(self, client):
        """Test accessing resources owned by another user"""
        # Create strategy as user A, try to access as user B
        pass


if __name__ == "__main__":
    print("Run with: pytest tests/e2e/test_error_handling.py -v")
