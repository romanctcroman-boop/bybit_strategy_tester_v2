import sys
import types
from types import SimpleNamespace

import pytest

# --- shims so test imports the task module without real DB/Celery/engine ---
mod = types.ModuleType("backend.celery_app")
mod.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = mod

mod_db = types.ModuleType("backend.database")


def _session_local():
    return SimpleNamespace(close=lambda: None)


mod_db.SessionLocal = _session_local


class _Backtest:
    pass


class _Base:
    pass


mod_db.Backtest = _Backtest
mod_db.Base = _Base
sys.modules["backend.database"] = mod_db

mod_be = types.ModuleType("backend.core.backtest_engine")


class _BE:
    def __init__(self, **kwargs):
        pass


mod_be.BacktestEngine = _BE
sys.modules["backend.core.backtest_engine"] = mod_be

mod_ea = types.ModuleType("backend.core.engine_adapter")


def _get_engine(name=None, **kwargs):
    return _BE()


mod_ea.get_engine = _get_engine
sys.modules["backend.core.engine_adapter"] = mod_ea

mod_ds = types.ModuleType("backend.services.data_service")


class _DS:
    def __init__(self, db=None):
        pass


mod_ds.DataService = _DS
sys.modules["backend.services.data_service"] = mod_ds

from backend.tasks.backtest_tasks import run_backtest_task


class DummyDataService:
    def __init__(self, backtest):
        self._backtest = backtest
        self.updated = False

    def get_backtest(self, backtest_id):
        return self._backtest

    def update_backtest(self, backtest_id, **fields):
        self._backtest.update(fields)
        self.updated = True

    def get_market_data(self, **kwargs):
        # No data available scenario
        return None


def test_no_market_data_raises_and_marks_failed(monkeypatch):
    backtest = {"id": 42, "status": "pending"}
    ds = DummyDataService(backtest)

    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)

    with pytest.raises(ValueError):
        run_backtest_task(
            None,
            backtest_id=42,
            strategy_config={"param": 1},
            symbol="BTCUSDT",
            interval="1h",
            start_date="2020-01-01",
            end_date="2020-01-02",
            initial_capital=10000.0,
        )

    assert backtest.get("status") == "failed"
    assert "error_message" in backtest
