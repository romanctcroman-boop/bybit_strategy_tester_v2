import sys
import types
from types import SimpleNamespace

import pandas as pd
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
        return pd.DataFrame([{"open": 1, "high": 1, "low": 1, "close": 1}])

    def update_backtest_results(self, backtest_id, **fields):
        self._backtest["results"] = fields


class EngineRaiser:
    def __init__(self, **kwargs):
        pass

    def run(self, data, strategy_config):
        raise RuntimeError("engine failure")


@pytest.fixture(autouse=True)
def default_shims(monkeypatch):
    # Default DataService used by import time in tasks will be replaced per-test
    monkeypatch.setattr(
        "backend.tasks.backtest_tasks.DataService",
        lambda db: DummyDataService({"id": 1, "status": "pending"}),
    )
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: EngineRaiser())


def make_self(retries, max_retries, raise_on_retry=False):
    req = SimpleNamespace(retries=retries)

    def retry(exc=None):
        if raise_on_retry:
            raise RuntimeError("retry-called")
        raise RuntimeError("retry-called")

    return SimpleNamespace(request=req, max_retries=max_retries, retry=retry)


def test_engine_exception_no_retry(monkeypatch):
    # DataService will record updates
    backtest = {"id": 10, "status": "pending"}
    ds = DummyDataService(backtest)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: EngineRaiser())

    # self with retries == max_retries -> no retry branch
    self = make_self(retries=1, max_retries=1)

    with pytest.raises(RuntimeError):
        run_backtest_task(
            self,
            backtest_id=10,
            strategy_config={"param": 1},
            symbol="BTCUSDT",
            interval="1h",
            start_date="2020-01-01",
            end_date="2020-01-02",
            initial_capital=10000.0,
        )

    # DataService should have updated status to failed
    assert backtest.get("status") == "failed"
    assert "error_message" in backtest


def test_engine_exception_triggers_retry(monkeypatch):
    backtest = {"id": 11, "status": "pending"}
    ds = DummyDataService(backtest)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: EngineRaiser())

    # self with retries < max_retries -> should call retry()
    self = make_self(retries=0, max_retries=1, raise_on_retry=True)

    with pytest.raises(RuntimeError) as excinfo:
        run_backtest_task(
            self,
            backtest_id=11,
            strategy_config={"param": 1},
            symbol="BTCUSDT",
            interval="1h",
            start_date="2020-01-01",
            end_date="2020-01-02",
            initial_capital=10000.0,
        )

    assert "retry-called" in str(excinfo.value)
    # DataService still updated to failed before retry
    assert backtest.get("status") == "failed"
