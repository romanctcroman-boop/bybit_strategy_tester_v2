import sys
import types
from types import SimpleNamespace

# Shim celery app early so module import doesn't fail
mod_ca = types.ModuleType("backend.celery_app")
mod_ca.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = mod_ca


def _prep_sys_modules_for_imports():
    # Minimal database module
    mod_db = types.ModuleType("backend.database")

    def _session_local():
        return SimpleNamespace(close=lambda: None)

    mod_db.SessionLocal = _session_local
    # Dummy ORM models to satisfy attribute access when tasks try to query
    mod_db.Optimization = object  # not used directly in our tests
    sys.modules["backend.database"] = mod_db

    # Engine adapter returning our dummy engine below
    mod_ea = types.ModuleType("backend.core.engine_adapter")

    class _Engine:
        def __init__(self, **kwargs):
            pass

        def run(self, data, strategy_config):
            # Score prefers higher 'a' and lower 'b' to create a clear optimum
            a = strategy_config.get("a", 0)
            b = strategy_config.get("b", 0)
            score = float(a) - float(b)
            return {
                "total_return": score,
                "sharpe_ratio": score,
                "max_drawdown": 0.0,
                "win_rate": 1.0,
                "total_trades": 1,
                "final_capital": 10000.0 + score,
            }

    def _get_engine(name=None, **kwargs):
        return _Engine()

    mod_ea.get_engine = _get_engine
    sys.modules["backend.core.engine_adapter"] = mod_ea

    # DataService with minimal API used by optimize tasks
    mod_ds = types.ModuleType("backend.services.data_service")

    class _DS:
        def __init__(self, db=None):
            pass

        def get_optimization(self, optimization_id):
            return {"id": optimization_id, "status": "pending"}

        def update_optimization(self, optimization_id, **fields):
            # no-op in tests
            return {"id": optimization_id, **fields}

        def get_market_data(self, **kwargs):
            # return small list of candle dicts
            return [
                {"timestamp": 0, "open": 1, "high": 1, "low": 1, "close": 1},
                {"timestamp": 1, "open": 1, "high": 1, "low": 1, "close": 1},
            ]

        # support context manager protocol used by tasks
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    mod_ds.DataService = _DS
    sys.modules["backend.services.data_service"] = mod_ds


def test_grid_search_minimal(monkeypatch):
    _prep_sys_modules_for_imports()
    from backend.tasks.optimize_tasks import grid_search_task

    # Dummy self to capture update_state calls
    calls = []

    class _Self:
        request = SimpleNamespace(retries=0)
        max_retries = 0

        def update_state(self, state, meta):
            calls.append((state, meta))

    # a in {0, 2}, b in {0, 1} -> best is a=2, b=0 for metric 'sharpe_ratio'
    res = grid_search_task(
        _Self(),
        optimization_id=7,
        strategy_config={"initial_capital": 10000.0},
        param_space={"a": [0, 2], "b": [0, 1]},
        symbol="BTCUSDT",
        interval="1",
        start_date="2024-01-01",
        end_date="2024-01-31",
        metric="sharpe_ratio",
    )

    assert res["status"] == "completed"
    assert res["best_params"] == {"a": 2, "b": 0}


def test_bayesian_minimal(monkeypatch):
    _prep_sys_modules_for_imports()

    # Stub BayesianOptimizer used inside the task function
    mod_bayes = types.ModuleType("backend.core.bayesian")

    class BayesianOptimizer:  # noqa: N801 (matching import name)
        def __init__(self, **kwargs):
            pass

        async def optimize_async(
            self, strategy_config, param_space, metric, direction, show_progress
        ):
            # return deterministic results
            return {
                "best_value": 1.23,
                "best_params": {"x": 10},
                "statistics": {"completed_trials": 2},
            }

        def get_importance(self):
            return {"x": 0.9}

    mod_bayes.BayesianOptimizer = BayesianOptimizer
    sys.modules["backend.core.bayesian"] = mod_bayes

    from backend.tasks.optimize_tasks import bayesian_optimization_task

    class _Self:
        request = SimpleNamespace(retries=0)
        max_retries = 0

        def update_state(self, state, meta):
            pass

    res = bayesian_optimization_task(
        _Self(),
        optimization_id=8,
        strategy_config={"initial_capital": 10000.0},
        param_space={"x": {"type": "int", "low": 1, "high": 10}},
        symbol="BTCUSDT",
        interval="1",
        start_date="2024-01-01",
        end_date="2024-01-10",
        n_trials=2,
        metric="sharpe_ratio",
        direction="maximize",
        n_jobs=1,
    )

    assert res["status"] == "completed"
    assert res["results"]["best_value"] == 1.23


def test_walk_forward_minimal(monkeypatch):
    _prep_sys_modules_for_imports()

    # Stub WalkForwardAnalyzer used inside the task function
    mod_wf = types.ModuleType("backend.core.walkforward")

    class WalkForwardAnalyzer:  # noqa: N801 (matching import name)
        def __init__(self, data, **kwargs):
            self.windows = [1, 2, 3]

        async def run_async(self, strategy_config, param_space, metric):
            return {"windows": [1, 2, 3], "summary": {"best": 1.0}}

    mod_wf.WalkForwardAnalyzer = WalkForwardAnalyzer
    sys.modules["backend.core.walkforward"] = mod_wf

    from backend.tasks.optimize_tasks import walk_forward_task

    class _Self:
        request = SimpleNamespace(retries=0)
        max_retries = 0

        def update_state(self, state, meta):
            pass

    res = walk_forward_task(
        _Self(),
        optimization_id=9,
        strategy_config={"initial_capital": 10000.0},
        param_space={"x": [1, 2]},
        symbol="BTCUSDT",
        interval="1",
        start_date="2024-01-01",
        end_date="2024-01-20",
        train_size=2,
        test_size=1,
        step_size=1,
        metric="sharpe_ratio",
    )

    assert res["status"] == "completed"
    assert res["method"] == "walk_forward"
