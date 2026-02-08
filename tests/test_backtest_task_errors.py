"""Tests for backtest task error handling.

Uses module-level stubs (identical to test_backtest_task.py) to avoid real
DB/Celery/engine dependencies.  Stubs are restored after import.
"""

import sys
import types
from types import SimpleNamespace

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Stub modules (same comprehensive set as test_backtest_task.py)
# ---------------------------------------------------------------------------

_STUB_KEYS = [
    "backend.celery_app",
    "backend.database",
    "backend.database.models",
    "backend.database.models.backtest",
    "backend.database.models.strategy",
    "backend.database.models.optimization",
    "backend.database.models.trade",
    "backend.database.models.chat_conversation",
    "backend.database.models.strategy_version",
    "backend.models",
    "backend.models.bybit_kline_audit",
    "backend.core.backtest_engine",
    "backend.core.engine_adapter",
    "backend.services.data_service",
]
_originals = {k: sys.modules.get(k) for k in _STUB_KEYS}

_celery_mod = types.ModuleType("backend.celery_app")
_celery_mod.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = _celery_mod

_db_mod = types.ModuleType("backend.database")
_db_mod.__path__ = []
_db_mod.SessionLocal = lambda: SimpleNamespace(close=lambda: None)
sys.modules["backend.database"] = _db_mod

_Backtest = type("Backtest", (), {})
_Strategy = type("Strategy", (), {})
_Optimization = type("Optimization", (), {})
_Trade = type("Trade", (), {})
_StrategyVersion = type("StrategyVersion", (), {})
_ChatConversation = type("ChatConversation", (), {})
_BybitKlineAudit = type("BybitKlineAudit", (), {})

_db_models = types.ModuleType("backend.database.models")
_db_models.__path__ = []
for _attr, _val in {
    "Backtest": _Backtest, "BacktestStatus": SimpleNamespace(),
    "Strategy": _Strategy, "StrategyType": SimpleNamespace(), "StrategyStatus": SimpleNamespace(),
    "Optimization": _Optimization, "OptimizationStatus": SimpleNamespace(), "OptimizationType": SimpleNamespace(),
    "Trade": _Trade, "TradeSide": SimpleNamespace(), "TradeStatus": SimpleNamespace(),
    "ChatConversation": _ChatConversation, "StrategyVersion": _StrategyVersion,
}.items():
    setattr(_db_models, _attr, _val)
sys.modules["backend.database.models"] = _db_models

_leaf_exports = {
    "backend.database.models.backtest": {"Backtest": _Backtest, "BacktestStatus": SimpleNamespace()},
    "backend.database.models.strategy": {"Strategy": _Strategy, "StrategyType": SimpleNamespace(), "StrategyStatus": SimpleNamespace()},
    "backend.database.models.optimization": {"Optimization": _Optimization, "OptimizationStatus": SimpleNamespace(), "OptimizationType": SimpleNamespace()},
    "backend.database.models.trade": {"Trade": _Trade, "TradeSide": SimpleNamespace(), "TradeStatus": SimpleNamespace()},
    "backend.database.models.chat_conversation": {"ChatConversation": _ChatConversation},
    "backend.database.models.strategy_version": {"StrategyVersion": _StrategyVersion},
}
for _modname, _exports in _leaf_exports.items():
    _m = types.ModuleType(_modname)
    for _a, _v in _exports.items():
        setattr(_m, _a, _v)
    sys.modules[_modname] = _m

_models_mod = types.ModuleType("backend.models")
_models_mod.__path__ = []
for _a, _v in {
    "Backtest": _Backtest, "BacktestStatus": SimpleNamespace(),
    "Strategy": _Strategy, "StrategyType": SimpleNamespace(), "StrategyStatus": SimpleNamespace(),
    "Optimization": _Optimization, "OptimizationStatus": SimpleNamespace(), "OptimizationType": SimpleNamespace(),
    "Trade": _Trade, "TradeSide": SimpleNamespace(), "TradeStatus": SimpleNamespace(),
    "ChatConversation": _ChatConversation, "StrategyVersion": _StrategyVersion,
    "BybitKlineAudit": _BybitKlineAudit, "MarketData": _BybitKlineAudit,
    "OptimizationResult": _Optimization,
}.items():
    setattr(_models_mod, _a, _v)
sys.modules["backend.models"] = _models_mod

_bka_mod = types.ModuleType("backend.models.bybit_kline_audit")
_bka_mod.BybitKlineAudit = _BybitKlineAudit
sys.modules["backend.models.bybit_kline_audit"] = _bka_mod

_be_mod = types.ModuleType("backend.core.backtest_engine")


class _BE:
    def __init__(self, **kwargs):
        pass


_be_mod.BacktestEngine = _BE
sys.modules["backend.core.backtest_engine"] = _be_mod

_ea_mod = types.ModuleType("backend.core.engine_adapter")
_ea_mod.get_engine = lambda name=None, **kwargs: _BE()
sys.modules["backend.core.engine_adapter"] = _ea_mod

_ds_mod = types.ModuleType("backend.services.data_service")
_ds_mod.DataService = type("DataService", (), {"__init__": lambda self, db=None: None})
sys.modules["backend.services.data_service"] = _ds_mod

# ---------------------------------------------------------------------------
from backend.tasks.backtest_tasks import run_backtest_task

for _key in _STUB_KEYS:
    if _originals[_key] is not None:
        sys.modules[_key] = _originals[_key]
    else:
        sys.modules.pop(_key, None)
# ---------------------------------------------------------------------------


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
    monkeypatch.setattr(
        "backend.tasks.backtest_tasks.DataService",
        lambda db: DummyDataService({"id": 1, "status": "pending"}),
    )
    monkeypatch.setattr(
        "backend.tasks.backtest_tasks.get_engine",
        lambda name, **k: EngineRaiser(),
    )


def make_self(retries, max_retries, raise_on_retry=False):
    req = SimpleNamespace(retries=retries)

    def retry(exc=None):
        if raise_on_retry:
            raise RuntimeError("retry-called")
        raise RuntimeError("retry-called")

    return SimpleNamespace(request=req, max_retries=max_retries, retry=retry)


def test_engine_exception_no_retry(monkeypatch):
    backtest = {"id": 10, "status": "pending"}
    ds = DummyDataService(backtest)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: EngineRaiser())

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

    assert backtest.get("status") == "failed"
    assert "error_message" in backtest


def test_engine_exception_triggers_retry(monkeypatch):
    backtest = {"id": 11, "status": "pending"}
    ds = DummyDataService(backtest)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: EngineRaiser())

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
    assert backtest.get("status") == "failed"
