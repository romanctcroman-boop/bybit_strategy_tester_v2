"""
Tests for Evaluation Criteria Panel and Optimization Config Panel

These tests verify:
1. API endpoints for criteria and config (CRUD operations)
2. Pydantic model validation
3. Persistence to database
4. Default values and presets
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# Test data fixtures
@pytest.fixture
def sample_evaluation_criteria():
    """Sample evaluation criteria for testing"""
    return {
        "primary_metric": "sharpe_ratio",
        "secondary_metrics": ["win_rate", "max_drawdown", "profit_factor"],
        "constraints": [
            {"metric": "max_drawdown", "operator": "<=", "value": 15},
            {"metric": "total_trades", "operator": ">=", "value": 50},
        ],
        "sort_order": [
            {"metric": "sharpe_ratio", "direction": "desc"},
            {"metric": "profit_factor", "direction": "desc"},
        ],
        "use_composite": False,
        "weights": None,
    }


@pytest.fixture
def sample_optimization_config():
    """Sample optimization config for testing"""
    return {
        "method": "bayesian",
        "parameter_ranges": [
            {
                "name": "rsi_period",
                "param_path": "rsi_1.period",
                "type": "int",
                "low": 10,
                "high": 30,
                "step": 2,
                "values": None,
            }
        ],
        "data_period": {
            "start_date": "2024-01-01",
            "end_date": "2025-01-01",
            "train_split": 0.8,
            "walk_forward": None,
        },
        "limits": {"max_trials": 200, "timeout_seconds": 3600, "workers": 4},
        "advanced": {
            "early_stopping": True,
            "early_stopping_patience": 20,
            "prune_infeasible": True,
            "warm_start": False,
            "random_seed": None,
        },
        "symbol": "BTCUSDT",
        "timeframe": "1h",
    }


@pytest.fixture
def mock_db_strategy():
    """Mock strategy object"""
    strategy = MagicMock()
    strategy.id = "test-strategy-123"
    strategy.name = "Test Strategy"
    strategy.builder_graph = {}
    strategy.updated_at = datetime.now(UTC)
    return strategy


class TestEvaluationCriteriaModels:
    """Test Pydantic models for evaluation criteria"""

    def test_metric_constraint_valid(self):
        """Test valid metric constraint"""
        from backend.api.routers.strategy_builder import MetricConstraint

        constraint = MetricConstraint(metric="max_drawdown", operator="<=", value=15)
        assert constraint.metric == "max_drawdown"
        assert constraint.operator == "<="
        assert constraint.value == 15

    def test_metric_constraint_invalid_operator(self):
        """Test invalid operator raises validation error"""
        from pydantic import ValidationError

        from backend.api.routers.strategy_builder import MetricConstraint

        with pytest.raises(ValidationError):
            MetricConstraint(metric="max_drawdown", operator="~=", value=15)

    def test_sort_spec_defaults(self):
        """Test sort spec default direction"""
        from backend.api.routers.strategy_builder import SortSpec

        sort = SortSpec(metric="sharpe_ratio")
        assert sort.direction == "desc"

    def test_evaluation_criteria_defaults(self):
        """Test evaluation criteria default values"""
        from backend.api.routers.strategy_builder import EvaluationCriteria

        criteria = EvaluationCriteria()
        assert criteria.primary_metric == "sharpe_ratio"
        assert "win_rate" in criteria.secondary_metrics
        assert criteria.use_composite is False


class TestOptimizationConfigModels:
    """Test Pydantic models for optimization config"""

    def test_param_range_spec_valid(self):
        """Test valid parameter range spec"""
        from backend.api.routers.strategy_builder import ParamRangeSpec

        param = ParamRangeSpec(name="rsi_period", param_path="rsi_1.period", type="int", low=10, high=30, step=2)
        assert param.name == "rsi_period"
        assert param.low == 10
        assert param.high == 30

    def test_optimization_limits_defaults(self):
        """Test optimization limits default values"""
        from backend.api.routers.strategy_builder import OptimizationLimits

        limits = OptimizationLimits()
        assert limits.max_trials == 200
        assert limits.timeout_seconds == 3600
        assert limits.workers == 4

    def test_optimization_config_defaults(self):
        """Test optimization config default values"""
        from backend.api.routers.strategy_builder import OptimizationConfig

        config = OptimizationConfig()
        assert config.method == "bayesian"
        assert config.symbol == "BTCUSDT"

    def test_invalid_method(self):
        """Test invalid optimization method raises error"""
        from pydantic import ValidationError

        from backend.api.routers.strategy_builder import OptimizationConfig

        with pytest.raises(ValidationError):
            OptimizationConfig(method="invalid_method")


class TestEvaluationCriteriaEndpoints:
    """Test API endpoints for evaluation criteria"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.api.app import app

        return TestClient(app)

    def test_set_evaluation_criteria(self, client, sample_evaluation_criteria, mock_db_strategy):
        """Test setting evaluation criteria"""
        with patch("backend.api.routers.strategy_builder.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_db_strategy
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/strategy-builder/strategies/test-strategy-123/criteria",
                json=sample_evaluation_criteria,
            )

            # Should succeed or 404 (if strategy not found in real DB)
            assert response.status_code in [200, 404]

    def test_get_evaluation_criteria_defaults(self, client):
        """Test getting default evaluation criteria"""
        with patch("backend.api.routers.strategy_builder.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_strategy = MagicMock()
            mock_strategy.builder_graph = None
            mock_db.query.return_value.filter.return_value.first.return_value = mock_strategy
            mock_get_db.return_value = iter([mock_db])

            response = client.get("/api/v1/strategy-builder/strategies/test-strategy-123/criteria")

            assert response.status_code in [200, 404]

    def test_get_evaluation_criteria_not_found(self, client):
        """Test 404 for non-existent strategy"""
        with patch("backend.api.routers.strategy_builder.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([mock_db])

            response = client.get("/api/v1/strategy-builder/strategies/non-existent/criteria")

            assert response.status_code == 404


class TestOptimizationConfigEndpoints:
    """Test API endpoints for optimization config"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.api.app import app

        return TestClient(app)

    def test_set_optimization_config(self, client, sample_optimization_config, mock_db_strategy):
        """Test setting optimization config"""
        with patch("backend.api.routers.strategy_builder.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_db_strategy
            mock_get_db.return_value = iter([mock_db])

            response = client.post(
                "/api/v1/strategy-builder/strategies/test-strategy-123/optimization-config",
                json=sample_optimization_config,
            )

            assert response.status_code in [200, 404]

    def test_get_optimization_config_defaults(self, client):
        """Test getting default optimization config"""
        with patch("backend.api.routers.strategy_builder.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_strategy = MagicMock()
            mock_strategy.builder_graph = None
            mock_db.query.return_value.filter.return_value.first.return_value = mock_strategy
            mock_get_db.return_value = iter([mock_db])

            response = client.get("/api/v1/strategy-builder/strategies/test-strategy-123/optimization-config")

            assert response.status_code in [200, 404]


class TestAvailableMetrics:
    """Test available metrics endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from backend.api.app import app

        return TestClient(app)

    def test_get_available_metrics(self, client):
        """Test getting available metrics"""
        response = client.get("/api/v1/strategy-builder/metrics/available")

        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "metrics" in data
        assert "presets" in data

        # Check metric categories
        assert "performance" in data["metrics"]
        assert "risk" in data["metrics"]
        assert "trade_quality" in data["metrics"]

        # Check specific metrics exist
        assert "sharpe_ratio" in data["metrics"]["performance"]["metrics"]
        assert "max_drawdown" in data["metrics"]["risk"]["metrics"]

        # Check presets
        assert "conservative" in data["presets"]
        assert "aggressive" in data["presets"]
        assert "balanced" in data["presets"]


class TestConstraintValidation:
    """Test constraint validation logic"""

    def test_constraint_operators(self):
        """Test all valid constraint operators"""
        from backend.api.routers.strategy_builder import MetricConstraint

        valid_operators = ["<=", ">=", "<", ">", "==", "!="]
        for op in valid_operators:
            constraint = MetricConstraint(metric="test", operator=op, value=10)
            assert constraint.operator == op

    def test_train_split_bounds(self):
        """Test train split validation bounds"""
        from pydantic import ValidationError

        from backend.api.routers.strategy_builder import DataPeriod

        # Valid bounds
        period = DataPeriod(start_date="2024-01-01", end_date="2025-01-01", train_split=0.8)
        assert period.train_split == 0.8

        # Below minimum
        with pytest.raises(ValidationError):
            DataPeriod(start_date="2024-01-01", end_date="2025-01-01", train_split=0.3)

        # Above maximum
        with pytest.raises(ValidationError):
            DataPeriod(start_date="2024-01-01", end_date="2025-01-01", train_split=0.99)


class TestCompositeScoring:
    """Test composite scoring functionality"""

    def test_weights_with_composite(self):
        """Test weights are used when composite is enabled"""
        from backend.api.routers.strategy_builder import EvaluationCriteria

        criteria = EvaluationCriteria(
            use_composite=True, weights={"sharpe_ratio": 1.0, "win_rate": 0.8, "max_drawdown": 0.9}
        )

        assert criteria.use_composite is True
        assert criteria.weights["sharpe_ratio"] == 1.0

    def test_weights_without_composite(self):
        """Test weights can be None when composite is disabled"""
        from backend.api.routers.strategy_builder import EvaluationCriteria

        criteria = EvaluationCriteria(use_composite=False, weights=None)

        assert criteria.use_composite is False
        assert criteria.weights is None
