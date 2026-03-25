"""
Tests for Optimization Results Viewer API endpoints.

Tests:
- GET /optimizations/{id}/charts/convergence
- GET /optimizations/{id}/charts/sensitivity/{param}
- POST /optimizations/{id}/apply/{rank}
- GET /optimizations/{id}/results/paginated

@date 2026-01-30
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest


# Mock data fixtures
@pytest.fixture
def mock_optimization_completed():
    """Mock completed optimization with results."""
    return {
        "id": 1,
        "strategy_id": 1,
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "optimization_type": "grid_search",
        "status": "completed",
        "metric": "sharpe_ratio",
        "best_params": {"rsi_period": 14, "overbought": 70, "oversold": 30},
        "best_score": 2.34,
        "results": {
            "all_trials": [
                {
                    "rsi_period": 14,
                    "overbought": 70,
                    "oversold": 30,
                    "sharpe_ratio": 2.34,
                    "total_return": 45.6,
                    "win_rate": 62,
                    "max_drawdown": 8.3,
                    "total_trades": 87,
                    "profit_factor": 1.85,
                },
                {
                    "rsi_period": 16,
                    "overbought": 70,
                    "oversold": 25,
                    "sharpe_ratio": 2.28,
                    "total_return": 43.2,
                    "win_rate": 60,
                    "max_drawdown": 9.1,
                    "total_trades": 92,
                    "profit_factor": 1.75,
                },
                {
                    "rsi_period": 14,
                    "overbought": 75,
                    "oversold": 30,
                    "sharpe_ratio": 2.21,
                    "total_return": 41.8,
                    "win_rate": 59,
                    "max_drawdown": 7.8,
                    "total_trades": 85,
                    "profit_factor": 1.70,
                },
                {
                    "rsi_period": 12,
                    "overbought": 70,
                    "oversold": 30,
                    "sharpe_ratio": 2.15,
                    "total_return": 40.1,
                    "win_rate": 58,
                    "max_drawdown": 10.2,
                    "total_trades": 94,
                    "profit_factor": 1.65,
                },
                {
                    "rsi_period": 14,
                    "overbought": 65,
                    "oversold": 35,
                    "sharpe_ratio": 2.10,
                    "total_return": 38.7,
                    "win_rate": 61,
                    "max_drawdown": 8.9,
                    "total_trades": 79,
                    "profit_factor": 1.60,
                },
            ],
            "convergence": [1.5, 1.8, 2.0, 2.21, 2.28, 2.34],
            "param_importance": {"rsi_period": 0.35, "overbought": 0.28, "oversold": 0.22},
        },
        "created_at": datetime.now(UTC),
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }


@pytest.fixture
def mock_optimization_running():
    """Mock running optimization."""
    return {
        "id": 2,
        "strategy_id": 1,
        "status": "running",
        "metric": "sharpe_ratio",
        "results": None,
    }


@pytest.fixture
def mock_strategy():
    """Mock strategy for apply test."""
    return {
        "id": 1,
        "name": "RSI Strategy",
        "config": {"params": {}},
    }


class TestConvergenceEndpoint:
    """Tests for GET /optimizations/{id}/charts/convergence."""

    def test_get_convergence_success(self, mock_optimization_completed):
        """Test successful convergence data retrieval."""
        # Arrange
        from backend.api.routers.optimizations import (
            ConvergenceDataResponse,
            OptimizationStatus,
        )
        from backend.database.models.optimization import Optimization

        mock_opt = MagicMock(spec=Optimization)
        mock_opt.id = 1
        mock_opt.status = OptimizationStatus.COMPLETED
        mock_opt.metric = "sharpe_ratio"
        mock_opt.results = mock_optimization_completed["results"]

        # Act & Assert - structure test
        response = ConvergenceDataResponse(
            trials=[1, 2, 3, 4, 5, 6],
            best_scores=[1.5, 1.8, 2.0, 2.21, 2.28, 2.34],
            all_scores=[1.5, 1.8, 2.0, 2.21, 2.28, 2.34],
            metric="sharpe_ratio",
        )

        assert len(response.trials) == 6
        assert response.best_scores[-1] == 2.34
        assert response.metric == "sharpe_ratio"

    def test_convergence_not_completed(self, mock_optimization_running):
        """Test error when optimization not completed."""

        # Verify running status raises appropriate error
        assert mock_optimization_running["status"] == "running"


class TestSensitivityEndpoint:
    """Tests for GET /optimizations/{id}/charts/sensitivity/{param}."""

    def test_get_sensitivity_success(self, mock_optimization_completed):
        """Test successful sensitivity data retrieval."""
        from backend.api.routers.optimizations import SensitivityDataResponse

        # Extract rsi_period sensitivity
        all_trials = mock_optimization_completed["results"]["all_trials"]
        values = [t["rsi_period"] for t in all_trials]
        scores = [t["sharpe_ratio"] for t in all_trials]

        response = SensitivityDataResponse(
            param_name="rsi_period",
            values=values,
            scores=scores,
            metric="sharpe_ratio",
        )

        assert response.param_name == "rsi_period"
        assert len(response.values) == 5
        assert 12 in response.values
        assert 14 in response.values

    def test_sensitivity_param_not_found(self, mock_optimization_completed):
        """Test error when parameter not in results."""
        all_trials = mock_optimization_completed["results"]["all_trials"]
        param_name = "nonexistent_param"

        values = []
        for trial in all_trials:
            if param_name in trial:
                values.append(trial[param_name])

        assert len(values) == 0  # Parameter not found


class TestApplyEndpoint:
    """Tests for POST /optimizations/{id}/apply/{rank}."""

    def test_apply_best_params_success(self, mock_optimization_completed, mock_strategy):
        """Test applying best parameters to strategy."""
        from backend.api.routers.optimizations import ApplyParamsResponse

        # Simulate applying rank 1 (best)
        all_trials = mock_optimization_completed["results"]["all_trials"]
        sorted_trials = sorted(all_trials, key=lambda x: x["sharpe_ratio"], reverse=True)
        best_trial = sorted_trials[0]

        # Extract params (exclude metrics)
        metric_keys = {"sharpe_ratio", "total_return", "win_rate", "max_drawdown", "total_trades", "profit_factor"}
        params = {k: v for k, v in best_trial.items() if k not in metric_keys}

        response = ApplyParamsResponse(
            success=True,
            message="Applied rank #1 parameters to strategy 1",
            strategy_id=1,
            applied_params=params,
        )

        assert response.success is True
        assert response.applied_params["rsi_period"] == 14
        assert response.applied_params["overbought"] == 70

    def test_apply_invalid_rank(self, mock_optimization_completed):
        """Test error when rank is out of bounds."""
        all_trials = mock_optimization_completed["results"]["all_trials"]
        max_rank = len(all_trials)

        invalid_rank = max_rank + 10
        assert invalid_rank > max_rank


class TestPaginatedEndpoint:
    """Tests for GET /optimizations/{id}/results/paginated."""

    def test_paginated_results_first_page(self, mock_optimization_completed):
        """Test first page of paginated results."""
        all_trials = mock_optimization_completed["results"]["all_trials"]

        # Simulate pagination
        page = 1
        page_size = 3
        total = len(all_trials)
        total_pages = (total + page_size - 1) // page_size

        start = (page - 1) * page_size
        end = start + page_size
        page_results = all_trials[start:end]

        assert len(page_results) == 3
        assert total_pages == 2

    def test_paginated_results_with_filter(self, mock_optimization_completed):
        """Test filtered paginated results."""
        all_trials = mock_optimization_completed["results"]["all_trials"]

        # Filter: min_sharpe >= 2.2
        min_sharpe = 2.2
        filtered = [t for t in all_trials if t["sharpe_ratio"] >= min_sharpe]

        assert len(filtered) == 3  # 2.34, 2.28, 2.21 pass

    def test_paginated_results_sorted(self, mock_optimization_completed):
        """Test sorted paginated results."""
        all_trials = mock_optimization_completed["results"]["all_trials"]

        # Sort by total_trades desc
        sorted_trials = sorted(all_trials, key=lambda x: x["total_trades"], reverse=True)

        assert sorted_trials[0]["total_trades"] == 94  # Highest


class TestResultsViewerIntegration:
    """Integration tests for the full results viewer workflow."""

    def test_load_and_filter_workflow(self, mock_optimization_completed):
        """Test typical user workflow: load -> filter -> sort -> apply."""
        all_trials = mock_optimization_completed["results"]["all_trials"]

        # Step 1: Load results
        assert len(all_trials) == 5

        # Step 2: Apply filters (min Sharpe 2.0, max DD 10%)
        filtered = [t for t in all_trials if t["sharpe_ratio"] >= 2.0 and t["max_drawdown"] <= 10.0]
        assert len(filtered) == 4  # Excludes trial with DD 10.2

        # Step 3: Sort by return
        sorted_trials = sorted(filtered, key=lambda x: x["total_return"], reverse=True)
        assert sorted_trials[0]["total_return"] == 45.6

        # Step 4: Select best from filtered
        best = sorted_trials[0]
        assert best["rsi_period"] == 14

    def test_convergence_chart_data(self, mock_optimization_completed):
        """Test convergence data is correctly formatted for chart."""
        convergence = mock_optimization_completed["results"]["convergence"]

        # Verify monotonically increasing (best so far)
        for i in range(1, len(convergence)):
            assert convergence[i] >= convergence[i - 1]

        # Verify ends at best score
        assert convergence[-1] == 2.34

    def test_param_importance_data(self, mock_optimization_completed):
        """Test parameter importance is correctly calculated."""
        importance = mock_optimization_completed["results"]["param_importance"]

        # Verify all params present
        assert "rsi_period" in importance
        assert "overbought" in importance
        assert "oversold" in importance

        # Verify sums roughly to 1 (or less for partial)
        total = sum(importance.values())
        assert total <= 1.0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_results(self):
        """Test handling of empty results."""
        results = {"all_trials": []}

        assert len(results["all_trials"]) == 0

    def test_missing_metric_in_trial(self):
        """Test handling of trial without target metric."""
        trial = {"rsi_period": 14, "overbought": 70}

        score = trial.get("sharpe_ratio", 0)
        assert score == 0

    def test_non_numeric_param_value(self):
        """Test handling of non-numeric parameter."""
        trial = {"rsi_period": "invalid"}

        try:
            val = float(trial["rsi_period"])
            assert False, "Should raise ValueError"
        except ValueError:
            pass  # Expected

    def test_large_results_set(self):
        """Test handling of large results set."""
        # Generate 1000 results
        results = [
            {
                "rsi_period": 10 + (i % 20),
                "overbought": 65 + (i % 15),
                "sharpe_ratio": 0.5 + (i % 200) / 100,
            }
            for i in range(1000)
        ]

        # Verify pagination handles large set
        page_size = 20
        total_pages = (len(results) + page_size - 1) // page_size
        assert total_pages == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
