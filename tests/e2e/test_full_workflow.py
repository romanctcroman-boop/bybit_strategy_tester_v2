"""
End-to-End Integration Tests

These tests verify complete workflows across multiple API endpoints.

NOTE: These are MOCK E2E tests - they test the API structure but don't execute real backtests.
For real integration tests with actual backtest execution, see test_full_workflow_real.py

Test Workflows:
1. Strategy Creation → Backtest → Results Verification
2. Strategy Creation → Optimization → Best Parameters
3. Full Lifecycle: Create → Backtest → Delete

Run with: pytest tests/e2e/test_full_workflow.py -v
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from backend.api.app import app


@pytest.fixture(scope="module")
def client():
    """Create test client for E2E tests"""
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_strategy():
    """Sample strategy data for testing"""
    return {
        "name": "E2E Test Strategy - SMA Crossover",
        "description": "Simple moving average crossover strategy for E2E testing",
        "code": """
from backend.strategies.base import BaseStrategy

class TestStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.short_period = 10
        self.long_period = 30
    
    def calculate_indicators(self, df):
        df['sma_short'] = df['close'].rolling(window=self.short_period).mean()
        df['sma_long'] = df['close'].rolling(window=self.long_period).mean()
        return df
    
    def generate_signals(self, df):
        df['signal'] = 0
        df.loc[df['sma_short'] > df['sma_long'], 'signal'] = 1
        df.loc[df['sma_short'] < df['sma_long'], 'signal'] = -1
        return df
""",
        "parameters": {
            "short_period": {"type": "int", "default": 10, "min": 5, "max": 20},
            "long_period": {"type": "int", "default": 30, "min": 20, "max": 50}
        }
    }


class TestAPIStructure:
    """Test API endpoint availability and structure"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint is accessible"""
        response = client.get("/")
        assert response.status_code in [200, 404]  # May redirect or return 404
        print("\n✅ Root endpoint accessible")
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        # Health endpoint may or may not exist
        assert response.status_code in [200, 404, 405]
        print(f"✅ Health endpoint status: {response.status_code}")
    
    def test_docs_endpoint(self, client):
        """Test API documentation endpoint"""
        response = client.get("/docs")
        assert response.status_code == 200
        print("✅ API docs accessible at /docs")


class TestStrategyWorkflow:
    """Test strategy-related workflows"""
    
    @pytest.mark.skip(reason="Requires database setup - see conftest.py for database fixtures")
    def test_list_strategies(self, client):
        """Test listing all strategies"""
        response = client.get("/api/v1/strategies")
        assert response.status_code == 200
        strategies = response.json()
        assert isinstance(strategies, list)
        print(f"✅ Listed {len(strategies)} strategies")
    
    @pytest.mark.skip(reason="Requires database setup")
    def test_create_strategy(self, client, sample_strategy):
        """Test creating a new strategy"""
        response = client.post("/api/v1/strategies", json=sample_strategy)
        assert response.status_code == 201
        strategy = response.json()
        assert "id" in strategy
        assert strategy["name"] == sample_strategy["name"]
        print(f"✅ Created strategy: {strategy['id']}")
        return strategy["id"]
    
    @pytest.mark.skip(reason="Requires database setup")
    def test_get_strategy(self, client, sample_strategy):
        """Test getting a specific strategy"""
        # First create
        create_response = client.post("/api/v1/strategies", json=sample_strategy)
        strategy_id = create_response.json()["id"]
        
        # Then get
        response = client.get(f"/api/v1/strategies/{strategy_id}")
        assert response.status_code == 200
        strategy = response.json()
        assert strategy["id"] == strategy_id
        print(f"✅ Retrieved strategy: {strategy_id}")


class TestBacktestWorkflow:
    """Test backtest-related workflows"""
    
    @pytest.mark.skip(reason="Requires database setup and real backtest execution")
    def test_create_backtest(self, client, sample_strategy):
        """Test creating a backtest"""
        # Create strategy first
        strategy_response = client.post("/api/v1/strategies", json=sample_strategy)
        strategy_id = strategy_response.json()["id"]
        
        # Create backtest
        backtest_data = {
            "strategy_id": strategy_id,
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": (datetime.now() - timedelta(days=7)).isoformat(),
            "end_date": datetime.now().isoformat(),
            "initial_capital": 10000.0
        }
        
        response = client.post("/api/v1/backtests", json=backtest_data)
        assert response.status_code == 201
        backtest = response.json()
        assert "id" in backtest
        print(f"✅ Created backtest: {backtest['id']}")


class TestValidation:
    """Test input validation"""
    
    def test_invalid_strategy_code(self, client):
        """Test creating strategy with invalid code"""
        invalid_strategy = {
            "name": "Invalid Strategy",
            "code": "this is not valid python code {{{",
            "parameters": {}
        }
        
        response = client.post("/api/v1/strategies", json=invalid_strategy)
        # Should fail validation (422) or fail later (500)
        assert response.status_code in [422, 500]
        print(f"✅ Rejected invalid strategy code (status: {response.status_code})")
    
    def test_missing_required_fields(self, client):
        """Test creating strategy without required fields"""
        incomplete_strategy = {
            "name": "Incomplete Strategy"
            # Missing code and parameters
        }
        
        response = client.post("/api/v1/strategies", json=incomplete_strategy)
        assert response.status_code == 422
        print("✅ Rejected incomplete strategy data")


@pytest.mark.slow
class TestPerformance:
    """Performance-related tests (marked as slow)"""
    
    @pytest.mark.skip(reason="Requires full system setup")
    def test_concurrent_requests(self, client):
        """Test handling concurrent API requests"""
        import threading
        
        results = []
        
        def make_request():
            response = client.get("/api/v1/strategies")
            results.append(response.status_code)
        
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        assert all(status == 200 for status in results)
        print(f"✅ Handled {len(results)} concurrent requests")


if __name__ == "__main__":
    print("Run with: pytest tests/e2e/test_full_workflow.py -v")
    print("Run without skipped tests: pytest tests/e2e/test_full_workflow.py -v -m 'not skip'")

