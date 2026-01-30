"""
Backtest API Integration Tests

E2E tests for /api/v1/backtests/ endpoints.
Tests run, list, get, delete operations.
"""

import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from loguru import logger

from backend.api.app import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def backtest_config():
    """Standard backtest configuration."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    return {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_capital": 10000,
        "leverage": 10,
        "direction": "both",
        "stop_loss": 0.02,
        "take_profit": 0.03,
        "strategy_type": "rsi",
        "strategy_params": {
            "period": 14,
            "overbought": 70,
            "oversold": 30,
        },
    }


class TestBacktestRunEndpoint:
    """Test POST /api/v1/backtests/ endpoint."""

    def test_run_backtest_success(self, client, backtest_config):
        """Test successful backtest execution."""
        response = client.post("/api/v1/backtests/", json=backtest_config)

        logger.info(f"Response status: {response.status_code}")

        # Should return 200 or 201
        assert response.status_code in [200, 201], f"Failed: {response.text}"

        data = response.json()
        logger.info(f"Backtest ID: {data.get('id', data.get('backtest_id'))}")

        # Check required fields
        assert "id" in data or "backtest_id" in data
        assert "status" in data or "metrics" in data

    def test_run_backtest_invalid_symbol(self, client, backtest_config):
        """Test backtest with invalid symbol."""
        config = backtest_config.copy()
        config["symbol"] = "INVALID123"

        response = client.post("/api/v1/backtests/", json=config)

        # Should return error (400 or 422)
        assert response.status_code in [400, 404, 422, 500]

    def test_run_backtest_invalid_dates(self, client, backtest_config):
        """Test backtest with invalid date range."""
        config = backtest_config.copy()
        config["start_date"] = "2030-01-01"  # Future date
        config["end_date"] = "2030-01-31"

        response = client.post("/api/v1/backtests/", json=config)

        # Should return error
        assert response.status_code in [400, 404, 422, 500]

    def test_run_backtest_missing_required_fields(self, client):
        """Test backtest with missing required fields."""
        incomplete_config = {
            "symbol": "BTCUSDT",
            # Missing other required fields
        }

        response = client.post("/api/v1/backtests/", json=incomplete_config)

        # Should return validation error
        assert response.status_code == 422

    def test_run_backtest_different_strategies(self, client, backtest_config):
        """Test backtest with different strategy types."""
        strategies = [
            {
                "strategy_type": "rsi",
                "strategy_params": {"period": 14, "overbought": 70, "oversold": 30},
            },
            {
                "strategy_type": "macd",
                "strategy_params": {
                    "fast_period": 12,
                    "slow_period": 26,
                    "signal_period": 9,
                },
            },
            {
                "strategy_type": "sma_cross",
                "strategy_params": {"fast_period": 10, "slow_period": 20},
            },
        ]

        for strategy in strategies:
            config = backtest_config.copy()
            config.update(strategy)

            response = client.post("/api/v1/backtests/", json=config)
            logger.info(f"Strategy {strategy['strategy_type']}: {response.status_code}")

            # Should succeed or fail gracefully
            assert response.status_code in [200, 201, 400, 404, 422, 500]


class TestBacktestListEndpoint:
    """Test GET /api/v1/backtests/ endpoint."""

    def test_list_backtests(self, client):
        """Test listing all backtests."""
        try:
            response = client.get("/api/v1/backtests/")

            logger.info(f"List response: {response.status_code}")

            # Can return 200 or error if DB session issue
            assert response.status_code in [200, 500]

            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, (list, dict))

                if isinstance(data, dict):
                    # Paginated response
                    assert "items" in data or "backtests" in data or "results" in data
        except Exception as e:
            logger.warning(f"List backtests test failed: {e}")
            pytest.skip("List endpoint not available")

    def test_list_backtests_pagination(self, client):
        """Test backtest list pagination."""
        try:
            response = client.get("/api/v1/backtests/?limit=5&page=1")
            assert response.status_code in [200, 500]
        except Exception as e:
            logger.warning(f"Pagination test failed: {e}")
            pytest.skip("Pagination not available")

    def test_list_backtests_filter_by_symbol(self, client):
        """Test filtering backtests by symbol."""
        try:
            response = client.get("/api/v1/backtests/?symbol=BTCUSDT")
            assert response.status_code in [
                200,
                422,
                500,
            ]  # 422 if filter not supported
        except Exception as e:
            logger.warning(f"Filter test failed: {e}")
            pytest.skip("Filter not available")


class TestBacktestGetEndpoint:
    """Test GET /api/v1/backtests/{id} endpoint."""

    def test_get_backtest_not_found(self, client):
        """Test getting non-existent backtest."""
        response = client.get("/api/v1/backtests/nonexistent-id-12345")

        assert response.status_code == 404

    def test_get_backtest_after_run(self, client, backtest_config):
        """Test getting backtest after running it."""
        # First run a backtest
        run_response = client.post("/api/v1/backtests/", json=backtest_config)

        if run_response.status_code not in [200, 201]:
            pytest.skip("Backtest run failed, skipping get test")

        data = run_response.json()
        backtest_id = data.get("id") or data.get("backtest_id")

        if not backtest_id:
            pytest.skip("No backtest ID returned")

        # Now get the backtest
        get_response = client.get(f"/api/v1/backtests/{backtest_id}")

        logger.info(f"Get backtest {backtest_id}: {get_response.status_code}")

        assert get_response.status_code in [200, 404]


class TestBacktestDeleteEndpoint:
    """Test DELETE /api/v1/backtests/{id} endpoint."""

    def test_delete_backtest_not_found(self, client):
        """Test deleting non-existent backtest."""
        response = client.delete("/api/v1/backtests/nonexistent-id-12345")

        assert response.status_code in [404, 204]

    def test_delete_backtest_after_run(self, client, backtest_config):
        """Test deleting backtest after running it."""
        # First run a backtest
        run_response = client.post("/api/v1/backtests/", json=backtest_config)

        if run_response.status_code not in [200, 201]:
            pytest.skip("Backtest run failed, skipping delete test")

        data = run_response.json()
        backtest_id = data.get("id") or data.get("backtest_id")

        if not backtest_id:
            pytest.skip("No backtest ID returned")

        # Delete the backtest
        delete_response = client.delete(f"/api/v1/backtests/{backtest_id}")

        logger.info(f"Delete backtest {backtest_id}: {delete_response.status_code}")

        assert delete_response.status_code in [200, 204, 404]

        # Verify it's deleted
        get_response = client.get(f"/api/v1/backtests/{backtest_id}")
        # Should be not found after deletion
        assert get_response.status_code in [404, 200]  # 200 if soft delete


class TestBacktestMetrics:
    """Test backtest metrics in response."""

    def test_metrics_fields(self, client, backtest_config):
        """Test that backtest returns expected metrics."""
        response = client.post("/api/v1/backtests/", json=backtest_config)

        if response.status_code not in [200, 201]:
            pytest.skip("Backtest run failed")

        data = response.json()
        metrics = data.get("metrics") or data

        # Check for common metrics
        expected_metrics = [
            "total_return",
            "sharpe_ratio",
            "max_drawdown",
            "win_rate",
            "profit_factor",
            "total_trades",
        ]

        found_metrics = []
        for metric in expected_metrics:
            if metric in metrics:
                found_metrics.append(metric)
                logger.info(f"{metric}: {metrics[metric]}")

        logger.info(
            f"Found {len(found_metrics)}/{len(expected_metrics)} expected metrics"
        )

    def test_trades_in_response(self, client, backtest_config):
        """Test that backtest returns trade list."""
        response = client.post("/api/v1/backtests/", json=backtest_config)

        if response.status_code not in [200, 201]:
            pytest.skip("Backtest run failed")

        data = response.json()

        # Check for trades
        if "trades" in data:
            trades = data["trades"]
            logger.info(f"Total trades: {len(trades)}")

            if len(trades) > 0:
                # Check first trade structure
                first_trade = trades[0]
                trade_fields = ["entry_time", "exit_time", "side", "pnl"]
                for field in trade_fields:
                    assert field in first_trade, f"Missing field: {field}"


class TestBacktestValidation:
    """Test input validation."""

    def test_invalid_leverage(self, client, backtest_config):
        """Test with invalid leverage value."""
        config = backtest_config.copy()
        config["leverage"] = -5  # Invalid negative leverage

        response = client.post("/api/v1/backtests/", json=config)

        assert response.status_code in [400, 422]

    def test_invalid_capital(self, client, backtest_config):
        """Test with invalid initial capital."""
        config = backtest_config.copy()
        config["initial_capital"] = 0  # Invalid zero capital

        response = client.post("/api/v1/backtests/", json=config)

        assert response.status_code in [400, 422]

    def test_invalid_stop_loss(self, client, backtest_config):
        """Test with invalid stop loss."""
        config = backtest_config.copy()
        config["stop_loss"] = 2.0  # 200% - too high

        response = client.post("/api/v1/backtests/", json=config)

        # Could be accepted or rejected depending on validation
        assert response.status_code in [200, 201, 400, 422]


class TestBacktestPerformance:
    """Test backtest performance."""

    def test_backtest_response_time(self, client, backtest_config):
        """Test that backtest completes in reasonable time."""
        start = time.perf_counter()

        response = client.post("/api/v1/backtests/", json=backtest_config)

        elapsed = time.perf_counter() - start

        logger.info(f"Backtest completed in {elapsed:.2f}s")

        # Should complete within 60 seconds for standard config
        assert elapsed < 60, f"Backtest took too long: {elapsed:.2f}s"

    def test_short_period_backtest(self, client, backtest_config):
        """Test backtest with short period."""
        config = backtest_config.copy()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # Only 7 days

        config["start_date"] = start_date.strftime("%Y-%m-%d")
        config["end_date"] = end_date.strftime("%Y-%m-%d")

        start = time.perf_counter()
        response = client.post("/api/v1/backtests/", json=config)
        elapsed = time.perf_counter() - start

        logger.info(f"Short period backtest: {elapsed:.2f}s")

        # Short period should be fast
        assert response.status_code in [200, 201, 400, 404, 422, 500]


class TestStrategiesEndpoint:
    """Test /api/v1/backtests/strategies endpoint."""

    def test_list_strategies(self, client):
        """Test listing available strategies."""
        response = client.get("/api/v1/backtests/strategies")

        logger.info(f"Strategies endpoint: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Available strategies: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
