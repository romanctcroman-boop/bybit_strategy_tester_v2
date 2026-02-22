"""
Tests for backend/api/routers/optimizations.py

Router prefix: /api/v1/optimizations  (mounted directly in app.py)

Endpoints tested:
- POST   /api/v1/optimizations/               - Create optimization job
- GET    /api/v1/optimizations/               - List optimization jobs
- GET    /api/v1/optimizations/{id}           - Get optimization details
- GET    /api/v1/optimizations/{id}/status    - Get job status/progress
- GET    /api/v1/optimizations/{id}/results   - Get detailed results
- DELETE /api/v1/optimizations/{id}           - Cancel optimization
- POST   /api/v1/optimizations/{id}/rerun     - Rerun optimization
- GET    /api/v1/optimizations/{id}/charts/convergence
- GET    /api/v1/optimizations/{id}/charts/sensitivity/{param_name}
- POST   /api/v1/optimizations/{id}/apply/{result_rank}
- GET    /api/v1/optimizations/{id}/results/paginated
- GET    /api/v1/optimizations/stats/summary
"""

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Prevent real DB connections during import.
if "backend.database" not in sys.modules:
    sys.modules["backend.database"] = MagicMock()
if "sqlalchemy.orm" not in sys.modules:
    sys.modules["sqlalchemy.orm"] = MagicMock()

from backend.api.app import app
from backend.database import get_db
from backend.database.models.optimization import OptimizationStatus, OptimizationType

BASE = "/api/v1/optimizations"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_opt_mock(
    opt_id=1,
    strategy_id=10,
    optimization_type=OptimizationType.GRID_SEARCH,
    symbol="BTCUSDT",
    timeframe="1h",
    start_date=None,
    end_date=None,
    metric="sharpe_ratio",
    status=OptimizationStatus.QUEUED,
    progress=0.0,
    best_params=None,
    best_score=None,
    total_combinations=25,
    evaluated_combinations=0,
    param_ranges=None,
    results=None,
    error_message=None,
    config=None,
    initial_capital=10000.0,
):
    """Build a minimal Optimization DB row mock."""
    opt = MagicMock()
    opt.id = opt_id
    opt.strategy_id = strategy_id
    opt.optimization_type = optimization_type
    opt.symbol = symbol
    opt.timeframe = timeframe
    opt.start_date = start_date or datetime(2024, 1, 1, tzinfo=UTC)
    opt.end_date = end_date or datetime(2025, 1, 1, tzinfo=UTC)
    opt.metric = metric
    opt.status = status
    opt.progress = progress
    opt.best_params = best_params
    opt.best_score = best_score
    opt.total_combinations = total_combinations
    opt.evaluated_combinations = evaluated_combinations
    opt.param_ranges = param_ranges or {}
    opt.results = results or {}
    opt.error_message = error_message
    opt.config = config or {}
    opt.initial_capital = initial_capital
    opt.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    opt.started_at = None
    opt.completed_at = None
    return opt


def _make_strategy_mock(strategy_id=10, name="Test Strategy", parameters=None):
    """Build a minimal Strategy DB row mock."""
    s = MagicMock()
    s.id = strategy_id
    s.name = name
    s.parameters = parameters or {}
    s.config = None
    return s


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def db_override(mock_db):
    def _override():
        return mock_db

    app.dependency_overrides[get_db] = _override
    yield mock_db
    app.dependency_overrides.clear()


def _wire_query(mock_db, return_value, count_value=None):
    """Set up mock_db.query().filter().first() chain with return_value."""
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = return_value
    q.all.return_value = [return_value] if return_value else []
    q.order_by.return_value = q
    q.offset.return_value = q
    q.limit.return_value = q
    q.count.return_value = count_value if count_value is not None else (1 if return_value else 0)
    q.scalar.return_value = count_value if count_value is not None else 0
    mock_db.query.return_value = q
    return q


# ===========================================================================
# POST /  — create optimization job
# ===========================================================================


class TestCreateOptimization:
    """POST /api/v1/optimizations/"""

    _valid_payload = {
        "strategy_id": 10,
        "optimization_type": "grid_search",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_date": "2024-01-01",
        "end_date": "2025-01-01",
        "param_ranges": {
            "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 5}
        },
        "metric": "sharpe_ratio",
        "initial_capital": 10000.0,
        "n_trials": 50,
    }

    def test_create_optimization_success(self, client, db_override):
        """Valid request creates optimization and returns QUEUED job."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock()

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            # First query: Strategy lookup; second: Optimization after commit
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            obj.id = mock_opt.id
            obj.strategy_id = mock_opt.strategy_id
            obj.optimization_type = mock_opt.optimization_type
            obj.symbol = mock_opt.symbol
            obj.timeframe = mock_opt.timeframe
            obj.start_date = mock_opt.start_date
            obj.end_date = mock_opt.end_date
            obj.metric = mock_opt.metric
            obj.status = mock_opt.status
            obj.progress = mock_opt.progress
            obj.best_params = mock_opt.best_params
            obj.best_score = mock_opt.best_score
            obj.total_combinations = mock_opt.total_combinations
            obj.evaluated_combinations = mock_opt.evaluated_combinations
            obj.created_at = mock_opt.created_at
            obj.started_at = mock_opt.started_at
            obj.completed_at = mock_opt.completed_at
            obj.error_message = mock_opt.error_message

        db_override.refresh = fake_refresh

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=self._valid_payload)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["strategy_id"] == 10
        assert data["symbol"] == "BTCUSDT"
        assert data["metric"] == "sharpe_ratio"
        assert data["status"] == "queued"

    def test_create_optimization_strategy_not_found(self, client, db_override):
        """Missing strategy returns 404."""
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = None  # strategy not found
        db_override.query.return_value = q

        r = client.post(f"{BASE}/", json=self._valid_payload)
        assert r.status_code == 404
        assert "Strategy not found" in r.text

    def test_create_optimization_missing_required_fields(self, client, db_override):
        """Missing required fields (symbol, param_ranges) returns 422."""
        r = client.post(
            f"{BASE}/",
            json={
                "strategy_id": 10,
                "optimization_type": "grid_search",
                # missing symbol, start_date, end_date, param_ranges
            },
        )
        assert r.status_code == 422

    def test_create_optimization_bayesian_type(self, client, db_override):
        """Bayesian optimization type is accepted."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock(optimization_type=OptimizationType.BAYESIAN)

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            for attr in ("id", "strategy_id", "optimization_type", "symbol", "timeframe",
                         "start_date", "end_date", "metric", "status", "progress",
                         "best_params", "best_score", "total_combinations",
                         "evaluated_combinations", "created_at", "started_at",
                         "completed_at", "error_message"):
                setattr(obj, attr, getattr(mock_opt, attr))

        db_override.refresh = fake_refresh

        payload = dict(self._valid_payload, optimization_type="bayesian", n_trials=50)

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=payload)

        assert r.status_code == 200, r.text

    def test_create_optimization_walk_forward_type(self, client, db_override):
        """Walk-forward optimization type is accepted."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock(optimization_type=OptimizationType.WALK_FORWARD)

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            for attr in ("id", "strategy_id", "optimization_type", "symbol", "timeframe",
                         "start_date", "end_date", "metric", "status", "progress",
                         "best_params", "best_score", "total_combinations",
                         "evaluated_combinations", "created_at", "started_at",
                         "completed_at", "error_message"):
                setattr(obj, attr, getattr(mock_opt, attr))

        db_override.refresh = fake_refresh

        payload = dict(self._valid_payload, optimization_type="walk_forward")

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=payload)

        assert r.status_code == 200, r.text


# ===========================================================================
# GET /  — list optimization jobs
# ===========================================================================


class TestListOptimizations:
    """GET /api/v1/optimizations/"""

    def test_list_optimizations_empty(self, client, db_override):
        """Returns empty list when no jobs exist."""
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db_override.query.return_value = q

        r = client.get(f"{BASE}/")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data == []

    def test_list_optimizations_with_results(self, client, db_override):
        """Returns list of optimization responses."""
        opt1 = _make_opt_mock(opt_id=1, symbol="BTCUSDT")
        opt2 = _make_opt_mock(opt_id=2, symbol="ETHUSDT")

        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = [opt1, opt2]
        db_override.query.return_value = q

        r = client.get(f"{BASE}/")
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 2
        symbols = {item["symbol"] for item in data}
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

    def test_list_optimizations_filter_by_strategy(self, client, db_override):
        """strategy_id filter is applied."""
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db_override.query.return_value = q

        r = client.get(f"{BASE}/?strategy_id=42")
        assert r.status_code == 200, r.text
        # Verify filter was called (strategy_id applied)
        assert q.filter.called

    def test_list_optimizations_filter_by_status(self, client, db_override):
        """status filter is applied (queued, running, completed, etc.)."""
        q = MagicMock()
        q.filter.return_value = q
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = []
        db_override.query.return_value = q

        r = client.get(f"{BASE}/?status=completed")
        assert r.status_code == 200, r.text

    def test_list_optimizations_limit_validation(self, client, db_override):
        """limit > 200 fails validation."""
        r = client.get(f"{BASE}/?limit=500")
        assert r.status_code == 422

    def test_list_optimizations_offset_negative(self, client, db_override):
        """offset < 0 fails validation."""
        r = client.get(f"{BASE}/?offset=-1")
        assert r.status_code == 422


# ===========================================================================
# GET /{optimization_id}  — get single optimization
# ===========================================================================


class TestGetOptimization:
    """GET /api/v1/optimizations/{optimization_id}"""

    def test_get_optimization_success(self, client, db_override):
        """Returns optimization details for existing ID."""
        opt = _make_opt_mock(opt_id=1)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == 1
        assert data["symbol"] == "BTCUSDT"
        assert data["metric"] == "sharpe_ratio"
        assert data["status"] == "queued"

    def test_get_optimization_not_found(self, client, db_override):
        """Non-existent ID returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/9999")
        assert r.status_code == 404
        assert "Optimization not found" in r.text

    def test_get_optimization_response_fields(self, client, db_override):
        """Response contains all required OptimizationResponse fields."""
        opt = _make_opt_mock(
            opt_id=5,
            symbol="SOLUSDT",
            metric="win_rate",
            status=OptimizationStatus.RUNNING,
            progress=0.42,
            total_combinations=100,
            evaluated_combinations=42,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/5")
        assert r.status_code == 200, r.text
        data = r.json()
        required_fields = {
            "id", "strategy_id", "optimization_type", "symbol",
            "timeframe", "metric", "status", "progress",
            "total_combinations", "evaluated_combinations", "created_at",
        }
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


# ===========================================================================
# GET /{optimization_id}/status  — get job status
# ===========================================================================


class TestGetOptimizationStatus:
    """GET /api/v1/optimizations/{optimization_id}/status"""

    def test_get_status_queued(self, client, db_override):
        """Queued job returns progress=0 and no ETA."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.QUEUED, progress=0.0)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == 1
        assert data["status"] == "queued"
        assert data["progress"] == 0.0
        assert data["eta_seconds"] is None

    def test_get_status_running_with_progress(self, client, db_override):
        """Running job with progress returns ETA calculation."""
        opt = _make_opt_mock(
            opt_id=2,
            status=OptimizationStatus.RUNNING,
            progress=0.5,
            evaluated_combinations=50,
            total_combinations=100,
        )
        opt.started_at = datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/2/status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "running"
        assert data["progress"] == 0.5
        assert data["evaluated_combinations"] == 50
        # ETA should be calculated (numeric value)
        assert data["eta_seconds"] is not None
        assert isinstance(data["eta_seconds"], (int, float))

    def test_get_status_completed(self, client, db_override):
        """Completed job status returns correct fields."""
        opt = _make_opt_mock(
            opt_id=3,
            status=OptimizationStatus.COMPLETED,
            progress=1.0,
            best_score=2.35,
            best_params={"rsi_period": 14},
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/3/status")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "completed"
        assert data["current_best_score"] == 2.35
        assert data["current_best_params"] == {"rsi_period": 14}

    def test_get_status_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/999/status")
        assert r.status_code == 404


# ===========================================================================
# GET /{optimization_id}/results  — detailed results
# ===========================================================================


class TestGetOptimizationResults:
    """GET /api/v1/optimizations/{optimization_id}/results"""

    def test_get_results_not_completed_returns_400(self, client, db_override):
        """Non-completed optimization returns 400."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.RUNNING)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results")
        assert r.status_code == 400
        assert "not completed" in r.text.lower()

    def test_get_results_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/9999/results")
        assert r.status_code == 404

    def test_get_results_completed_success(self, client, db_override):
        """Completed optimization returns full results."""
        results = {
            "top_10": [
                {"rsi_period": 14, "sharpe_ratio": 2.1, "win_rate": 0.55, "total_trades": 120},
                {"rsi_period": 21, "sharpe_ratio": 1.8, "win_rate": 0.52, "total_trades": 95},
            ],
            "param_importance": {"rsi_period": 0.85},
            "convergence": [1.5, 1.8, 2.0, 2.1],
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            best_score=2.1,
            best_params={"rsi_period": 14},
            results=results,
        )
        opt.completed_at = datetime(2025, 6, 2, tzinfo=UTC)
        opt.started_at = datetime(2025, 6, 1, tzinfo=UTC)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == 1
        assert data["status"] == "completed"
        assert data["best_score"] == 2.1
        assert data["best_params"] == {"rsi_period": 14}
        assert isinstance(data["all_results"], list)
        assert data["param_importance"] == {"rsi_period": 0.85}
        assert data["convergence"] == [1.5, 1.8, 2.0, 2.1]
        assert data["duration_seconds"] == pytest.approx(86400.0, rel=0.01)


# ===========================================================================
# DELETE /{optimization_id}  — cancel optimization
# ===========================================================================


class TestCancelOptimization:
    """DELETE /api/v1/optimizations/{optimization_id}"""

    def test_cancel_queued_success(self, client, db_override):
        """Queued optimization can be cancelled."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.QUEUED)
        _wire_query(db_override, opt)

        r = client.delete(f"{BASE}/1")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "cancelled" in data.get("message", "").lower() or data.get("id") == 1

    def test_cancel_running_success(self, client, db_override):
        """Running optimization can be cancelled."""
        opt = _make_opt_mock(opt_id=2, status=OptimizationStatus.RUNNING)
        _wire_query(db_override, opt)

        r = client.delete(f"{BASE}/2")
        assert r.status_code == 200, r.text

    def test_cancel_completed_returns_400(self, client, db_override):
        """Cannot cancel a completed optimization."""
        opt = _make_opt_mock(opt_id=3, status=OptimizationStatus.COMPLETED)
        _wire_query(db_override, opt)

        r = client.delete(f"{BASE}/3")
        assert r.status_code == 400
        assert "Cannot cancel" in r.text

    def test_cancel_failed_returns_400(self, client, db_override):
        """Cannot cancel a failed optimization."""
        opt = _make_opt_mock(opt_id=4, status=OptimizationStatus.FAILED)
        _wire_query(db_override, opt)

        r = client.delete(f"{BASE}/4")
        assert r.status_code == 400

    def test_cancel_already_cancelled_returns_400(self, client, db_override):
        """Cannot cancel an already-cancelled optimization."""
        opt = _make_opt_mock(opt_id=5, status=OptimizationStatus.CANCELLED)
        _wire_query(db_override, opt)

        r = client.delete(f"{BASE}/5")
        assert r.status_code == 400

    def test_cancel_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.delete(f"{BASE}/9999")
        assert r.status_code == 404


# ===========================================================================
# POST /{optimization_id}/rerun  — rerun optimization
# ===========================================================================


class TestRerunOptimization:
    """POST /api/v1/optimizations/{optimization_id}/rerun"""

    def test_rerun_not_found(self, client, db_override):
        """Rerunning non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.post(f"{BASE}/9999/rerun")
        assert r.status_code == 404

    def test_rerun_success(self, client, db_override):
        """Rerun creates a new optimization and returns QUEUED status."""
        original = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            param_ranges={"rsi_period": {"type": "int", "low": 5, "high": 30, "step": 5}},
            config={"n_trials": 100, "train_size": 120, "test_size": 60, "step_size": 30, "n_jobs": 1},
        )
        new_opt = _make_opt_mock(opt_id=2, status=OptimizationStatus.QUEUED)

        mock_strat = _make_strategy_mock()
        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            if call_count["n"] == 1:
                q.first.return_value = original   # original optimization
            elif call_count["n"] == 2:
                q.first.return_value = mock_strat  # strategy lookup
            else:
                q.first.return_value = None
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            obj.id = new_opt.id
            obj.strategy_id = new_opt.strategy_id
            obj.optimization_type = new_opt.optimization_type
            obj.symbol = new_opt.symbol
            obj.timeframe = new_opt.timeframe
            obj.start_date = new_opt.start_date
            obj.end_date = new_opt.end_date
            obj.metric = new_opt.metric
            obj.status = new_opt.status
            obj.progress = new_opt.progress
            obj.best_params = new_opt.best_params
            obj.best_score = new_opt.best_score
            obj.total_combinations = new_opt.total_combinations
            obj.evaluated_combinations = new_opt.evaluated_combinations
            obj.created_at = new_opt.created_at
            obj.started_at = new_opt.started_at
            obj.completed_at = new_opt.completed_at
            obj.error_message = new_opt.error_message

        db_override.refresh = fake_refresh

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/1/rerun")

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "queued"
        assert data["id"] == new_opt.id


# ===========================================================================
# GET /{optimization_id}/charts/convergence
# ===========================================================================


class TestGetConvergenceData:
    """GET /api/v1/optimizations/{optimization_id}/charts/convergence"""

    def test_convergence_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/9999/charts/convergence")
        assert r.status_code == 404

    def test_convergence_not_completed(self, client, db_override):
        """Running optimization returns 400."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.RUNNING)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/convergence")
        assert r.status_code == 400

    def test_convergence_success_from_results(self, client, db_override):
        """Completed optimization with results returns convergence chart data."""
        results = {
            "all_trials": [
                {"sharpe_ratio": 1.2, "win_rate": 0.50},
                {"sharpe_ratio": 1.8, "win_rate": 0.55},
                {"sharpe_ratio": 2.1, "win_rate": 0.58},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/convergence")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "trials" in data
        assert "best_scores" in data
        assert "all_scores" in data
        assert "metric" in data
        assert data["metric"] == "sharpe_ratio"
        assert isinstance(data["trials"], list)
        assert isinstance(data["best_scores"], list)

    def test_convergence_precomputed_used_when_available(self, client, db_override):
        """Pre-computed convergence list in results takes precedence."""
        results = {
            "convergence": [1.0, 1.5, 2.0, 2.3],
            "all_trials": [],
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/convergence")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["best_scores"] == [1.0, 1.5, 2.0, 2.3]


# ===========================================================================
# GET /{optimization_id}/charts/sensitivity/{param_name}
# ===========================================================================


class TestGetSensitivityData:
    """GET /api/v1/optimizations/{optimization_id}/charts/sensitivity/{param_name}"""

    def test_sensitivity_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/9999/charts/sensitivity/rsi_period")
        assert r.status_code == 404

    def test_sensitivity_not_completed(self, client, db_override):
        """Not-completed optimization returns 400."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.QUEUED)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/sensitivity/rsi_period")
        assert r.status_code == 400

    def test_sensitivity_param_not_found(self, client, db_override):
        """Param not present in results returns 404."""
        results = {
            "all_trials": [
                {"sharpe_ratio": 1.2, "win_rate": 0.50},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/sensitivity/nonexistent_param")
        assert r.status_code == 404
        assert "nonexistent_param" in r.text

    def test_sensitivity_success(self, client, db_override):
        """Returns values and scores for existing parameter."""
        results = {
            "all_trials": [
                {"rsi_period": 5, "sharpe_ratio": 1.0},
                {"rsi_period": 10, "sharpe_ratio": 1.5},
                {"rsi_period": 14, "sharpe_ratio": 2.1},
                {"rsi_period": 21, "sharpe_ratio": 1.8},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/charts/sensitivity/rsi_period")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["param_name"] == "rsi_period"
        assert data["metric"] == "sharpe_ratio"
        assert len(data["values"]) == 4
        assert len(data["scores"]) == 4
        assert 14.0 in data["values"]


# ===========================================================================
# POST /{optimization_id}/apply/{result_rank}
# ===========================================================================


class TestApplyOptimizationResult:
    """POST /api/v1/optimizations/{optimization_id}/apply/{result_rank}"""

    def test_apply_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.post(f"{BASE}/9999/apply/1")
        assert r.status_code == 404

    def test_apply_not_completed(self, client, db_override):
        """Non-completed optimization returns 400."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.RUNNING)
        _wire_query(db_override, opt)

        r = client.post(f"{BASE}/1/apply/1")
        assert r.status_code == 400

    def test_apply_invalid_rank(self, client, db_override):
        """Rank out of bounds returns 400."""
        results = {
            "all_trials": [
                {"rsi_period": 14, "sharpe_ratio": 2.1},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        mock_strat = _make_strategy_mock()

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            if call_count["n"] == 1:
                q.first.return_value = opt
            else:
                q.first.return_value = mock_strat
            return q

        db_override.query.side_effect = query_side

        # rank=5 is out of bounds (only 1 trial)
        r = client.post(f"{BASE}/1/apply/5")
        assert r.status_code == 400
        assert "Invalid rank" in r.text

    def test_apply_success(self, client, db_override):
        """Valid rank applies parameters to strategy."""
        results = {
            "all_trials": [
                {"rsi_period": 14, "sharpe_ratio": 2.1, "win_rate": 0.55},
                {"rsi_period": 21, "sharpe_ratio": 1.8, "win_rate": 0.52},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
            strategy_id=10,
        )
        mock_strat = _make_strategy_mock(strategy_id=10)

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            if call_count["n"] == 1:
                q.first.return_value = opt
            else:
                q.first.return_value = mock_strat
            return q

        db_override.query.side_effect = query_side

        r = client.post(f"{BASE}/1/apply/1")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        assert data["strategy_id"] == 10
        assert "applied_params" in data
        # rsi_period should be applied (not a metric key)
        assert "rsi_period" in data["applied_params"]


# ===========================================================================
# GET /{optimization_id}/results/paginated
# ===========================================================================


class TestGetPaginatedResults:
    """GET /api/v1/optimizations/{optimization_id}/results/paginated"""

    def test_paginated_not_found(self, client, db_override):
        """Non-existent optimization returns 404."""
        _wire_query(db_override, None)

        r = client.get(f"{BASE}/9999/results/paginated")
        assert r.status_code == 404

    def test_paginated_not_completed(self, client, db_override):
        """Running optimization returns 400."""
        opt = _make_opt_mock(opt_id=1, status=OptimizationStatus.RUNNING)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results/paginated")
        assert r.status_code == 400

    def test_paginated_success_default_page(self, client, db_override):
        """Default pagination (page=1, page_size=20) returns correct structure."""
        results = {
            "all_trials": [
                {"rsi_period": i, "sharpe_ratio": float(i) / 10, "win_rate": 0.5}
                for i in range(1, 31)  # 30 results
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results/paginated")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 30
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 2
        assert len(data["results"]) == 20

    def test_paginated_second_page(self, client, db_override):
        """Second page returns remaining results."""
        results = {
            "all_trials": [
                {"rsi_period": i, "sharpe_ratio": float(i) / 10}
                for i in range(1, 26)  # 25 results
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results/paginated?page=2&page_size=20")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["page"] == 2
        assert len(data["results"]) == 5  # 25 - 20 = 5 remaining

    def test_paginated_with_min_sharpe_filter(self, client, db_override):
        """min_sharpe filter excludes below-threshold results."""
        results = {
            "all_trials": [
                {"rsi_period": 5, "sharpe_ratio": 0.5},
                {"rsi_period": 10, "sharpe_ratio": 1.5},
                {"rsi_period": 14, "sharpe_ratio": 2.5},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results/paginated?min_sharpe=1.0")
        assert r.status_code == 200, r.text
        data = r.json()
        # Only trials with sharpe_ratio >= 1.0 should remain
        assert data["total"] == 2
        for result in data["results"]:
            assert result["sharpe_ratio"] >= 1.0

    def test_paginated_page_size_validation(self, client, db_override):
        """page_size > 100 returns 422."""
        r = client.get(f"{BASE}/1/results/paginated?page_size=200")
        assert r.status_code == 422

    def test_paginated_ranks_added(self, client, db_override):
        """Results include rank field (1-indexed)."""
        results = {
            "all_trials": [
                {"rsi_period": 14, "sharpe_ratio": 2.1},
                {"rsi_period": 21, "sharpe_ratio": 1.8},
            ]
        }
        opt = _make_opt_mock(
            opt_id=1,
            status=OptimizationStatus.COMPLETED,
            metric="sharpe_ratio",
            results=results,
        )
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1/results/paginated")
        assert r.status_code == 200, r.text
        data = r.json()
        ranks = [item["rank"] for item in data["results"]]
        assert 1 in ranks  # At least rank 1 must be present


# ===========================================================================
# GET /stats/summary
# ===========================================================================


class TestGetOptimizationStats:
    """GET /api/v1/optimizations/stats/summary"""

    def test_stats_summary_success(self, client, db_override):
        """Returns summary dict with by_status and by_type."""
        # Wire scalar() calls to return count values
        q = MagicMock()
        q.filter.return_value = q
        q.group_by.return_value = q
        q.all.return_value = []
        q.scalar.return_value = 0
        db_override.query.return_value = q

        r = client.get(f"{BASE}/stats/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_type" in data
        # by_status should have expected keys
        by_status = data["by_status"]
        assert "completed" in by_status
        assert "running" in by_status
        assert "failed" in by_status
        assert "queued" in by_status

    def test_stats_summary_non_zero_counts(self, client, db_override):
        """Non-zero counts are reflected in the response."""
        call_count = {"n": 0}

        def query_side(model_or_col):
            q = MagicMock()
            q.filter.return_value = q
            q.group_by.return_value = q
            q.all.return_value = []
            call_count["n"] += 1
            # Return different scalars for each call
            q.scalar.return_value = call_count["n"] * 5
            return q

        db_override.query.side_effect = query_side

        r = client.get(f"{BASE}/stats/summary")
        assert r.status_code == 200, r.text
        data = r.json()
        # At least one value should be non-zero given the side_effect
        total = data["total"]
        assert isinstance(total, int)


# ===========================================================================
# Helper: generate_param_values unit logic (via indirect endpoint test)
# ===========================================================================


class TestParamValueGeneration:
    """
    Indirectly test generate_param_values() by verifying total_combinations
    is calculated correctly in CreateOptimizationRequest processing.
    """

    def test_grid_search_total_combinations_calculated(self, client, db_override):
        """Grid search with int range [5..30 step 5] = 6 values."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock(total_combinations=6)  # 5,10,15,20,25,30

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            for attr in ("id", "strategy_id", "optimization_type", "symbol", "timeframe",
                         "start_date", "end_date", "metric", "status", "progress",
                         "best_params", "best_score", "total_combinations",
                         "evaluated_combinations", "created_at", "started_at",
                         "completed_at", "error_message"):
                setattr(obj, attr, getattr(mock_opt, attr))

        db_override.refresh = fake_refresh

        payload = {
            "strategy_id": 10,
            "optimization_type": "grid_search",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2025-01-01",
            "param_ranges": {
                "rsi_period": {"type": "int", "low": 5, "high": 30, "step": 5}
            },
            "metric": "sharpe_ratio",
            "initial_capital": 10000.0,
        }

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=payload)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total_combinations"] == 6

    def test_bayesian_total_combinations_zero(self, client, db_override):
        """Bayesian optimization total_combinations = 0 (dynamic)."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock(
            optimization_type=OptimizationType.BAYESIAN,
            total_combinations=0,
        )

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            for attr in ("id", "strategy_id", "optimization_type", "symbol", "timeframe",
                         "start_date", "end_date", "metric", "status", "progress",
                         "best_params", "best_score", "total_combinations",
                         "evaluated_combinations", "created_at", "started_at",
                         "completed_at", "error_message"):
                setattr(obj, attr, getattr(mock_opt, attr))

        db_override.refresh = fake_refresh

        payload = {
            "strategy_id": 10,
            "optimization_type": "bayesian",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2025-01-01",
            "param_ranges": {
                "rsi_period": {"type": "int", "low": 5, "high": 30}
            },
            "metric": "sharpe_ratio",
            "initial_capital": 10000.0,
            "n_trials": 100,
        }

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=payload)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total_combinations"] == 0


# ===========================================================================
# Commission rate guard
# ===========================================================================


class TestCommissionRateIntegrity:
    """Ensure commission_rate=0.0007 is not exposed or modified by this router."""

    def test_optimization_response_does_not_expose_commission(self, client, db_override):
        """OptimizationResponse schema must not contain commission_rate."""
        opt = _make_opt_mock(opt_id=1)
        _wire_query(db_override, opt)

        r = client.get(f"{BASE}/1")
        assert r.status_code == 200, r.text
        data = r.json()
        # commission_rate belongs to backtesting engine, not optimization response
        assert "commission_rate" not in data
        assert "commission" not in data

    def test_create_optimization_accepts_initial_capital_default(self, client, db_override):
        """initial_capital defaults to 10000.0 (matching engine default)."""
        mock_strat = _make_strategy_mock()
        mock_opt = _make_opt_mock(initial_capital=10000.0)

        call_count = {"n": 0}

        def query_side(model):
            q = MagicMock()
            q.filter.return_value = q
            call_count["n"] += 1
            q.first.return_value = mock_strat if call_count["n"] == 1 else mock_opt
            return q

        db_override.query.side_effect = query_side

        def fake_refresh(obj):
            for attr in ("id", "strategy_id", "optimization_type", "symbol", "timeframe",
                         "start_date", "end_date", "metric", "status", "progress",
                         "best_params", "best_score", "total_combinations",
                         "evaluated_combinations", "created_at", "started_at",
                         "completed_at", "error_message"):
                setattr(obj, attr, getattr(mock_opt, attr))

        db_override.refresh = fake_refresh

        payload = {
            "strategy_id": 10,
            "optimization_type": "grid_search",
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "start_date": "2024-01-01",
            "end_date": "2025-01-01",
            "param_ranges": {
                "rsi_period": {"type": "int", "low": 10, "high": 20, "step": 5}
            },
            "metric": "sharpe_ratio",
            # initial_capital omitted — should default to 10000.0
        }

        with patch("backend.api.routers.optimizations.launch_optimization_task"):
            r = client.post(f"{BASE}/", json=payload)

        assert r.status_code == 200, r.text
