import sys
import types
from types import SimpleNamespace

import pytest

# Create a dummy backend.celery_app module so importing tasks in tests doesn't fail
mod = types.ModuleType("backend.celery_app")
mod.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = mod

# Provide a dummy backend.database module so tasks can import SessionLocal and Backtest
mod_db = types.ModuleType("backend.database")
def _session_local():
    return SimpleNamespace(close=lambda: None)
mod_db.SessionLocal = _session_local
class _Backtest:
    pass
mod_db.Backtest = _Backtest
sys.modules["backend.database"] = mod_db

# Provide a dummy backend.core.backtest_engine so engine_adapter imports in tests
mod_be = types.ModuleType("backend.core.backtest_engine")
class _BE:
    def __init__(self, **kwargs):
        pass
mod_be.BacktestEngine = _BE
sys.modules["backend.core.backtest_engine"] = mod_be

# Provide a minimal engine_adapter module used by the tasks (avoids importing real engine)
mod_ea = types.ModuleType("backend.core.engine_adapter")
def _get_engine(name=None, **kwargs):
    return _BE()
mod_ea.get_engine = _get_engine
sys.modules["backend.core.engine_adapter"] = mod_ea

# Provide a dummy backend.services.data_service module
mod_ds = types.ModuleType("backend.services.data_service")
class _DS:
    def __init__(self, db):
        pass
mod_ds.DataService = _DS
sys.modules["backend.services.data_service"] = mod_ds

import pandas as pd

from backend.tasks.backtest_tasks import run_backtest_task


class DummyDataService:
    def __init__(self, backtest):
        self._backtest = backtest

    def get_backtest(self, backtest_id):
        return self._backtest

    def update_backtest(self, backtest_id, **fields):
        self._backtest.update(fields)

    def get_market_data(self, **kwargs):
        # small dataframe
        return pd.DataFrame([{"open": 1, "high": 1, "low": 1, "close": 1}])

    def update_backtest_results(self, backtest_id, **fields):
        self._backtest["results"] = fields


class DummyEngine:
    def __init__(self, **kwargs):
        pass

    def run(self, data, strategy_config):
        return {
            "final_capital": 11000.0,
            "total_return": 0.1,
            "total_trades": 1,
            "winning_trades": 1,
            "losing_trades": 0,
            "win_rate": 1.0,
            "sharpe_ratio": 1.2,
            "max_drawdown": 0.01,
        }


@pytest.fixture(autouse=True)
def patch_services(monkeypatch):
    # Patch DataService used inside tasks
    def _make_ds(db):
        # returns DummyDataService with a mutable dict representing backtest
        return DummyDataService({"id": 1, "status": "pending"})

    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: _make_ds(db))
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: DummyEngine())


def test_run_backtest_happy_path():
    res = run_backtest_task(
        None,
        backtest_id=1,
        strategy_config={"param": 1},
        symbol="BTCUSDT",
        interval="1h",
        start_date="2020-01-01",
        end_date="2020-01-02",
        initial_capital=10000.0,
    )

    assert res["status"] == "completed"
    assert res["backtest_id"] == 1


def test_run_backtest_idempotent_completed(monkeypatch):
    # DataService returns already completed backtest
    bs = {"id": 2, "status": "completed"}

    def _make_ds2(db):
        return DummyDataService(bs)

    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: _make_ds2(db))
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: DummyEngine())

    res = run_backtest_task(
        None,
        backtest_id=2,
        strategy_config={"param": 1},
        symbol="BTCUSDT",
        interval="1h",
        start_date="2020-01-01",
        end_date="2020-01-02",
        initial_capital=10000.0,
    )

    assert res["status"] == "completed"
