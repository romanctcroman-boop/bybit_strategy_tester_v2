"""Tests for backtest Celery tasks.

Uses module-level stubs to avoid real DB/Celery/engine dependencies.
IMPORTANT: stubs are restored after import to prevent polluting sys.modules.
"""

import sys
import types
from types import SimpleNamespace

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Stub modules that ``backend.tasks`` needs at import time.
#
#   backend.tasks.__init__ imports both backtest_tasks and optimize_tasks.
#   optimize_tasks imports backend.models which re-exports everything from
#   backend.database.models and backend.models.bybit_kline_audit.
#
# We snapshot any real modules beforehand and restore them once the import
# is complete so that downstream tests see the real packages.
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

# --- celery ---
_celery_mod = types.ModuleType("backend.celery_app")
_celery_mod.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = _celery_mod

# --- backend.database (package) ---
_db_mod = types.ModuleType("backend.database")
_db_mod.__path__ = []
_db_mod.SessionLocal = lambda: SimpleNamespace(close=lambda: None)
sys.modules["backend.database"] = _db_mod

# --- Dummy ORM classes ---
_Backtest = type("Backtest", (), {})
_Strategy = type("Strategy", (), {})
_Optimization = type("Optimization", (), {})
_Trade = type("Trade", (), {})
_StrategyVersion = type("StrategyVersion", (), {})
_ChatConversation = type("ChatConversation", (), {})
_BybitKlineAudit = type("BybitKlineAudit", (), {})

# --- backend.database.models (package) ---
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

# --- backend.database.models leaf modules ---
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

# --- backend.models (re-export layer) ---
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

# --- backend.core.backtest_engine ---
_be_mod = types.ModuleType("backend.core.backtest_engine")


class _BE:
    def __init__(self, **kwargs):
        pass


_be_mod.BacktestEngine = _BE
sys.modules["backend.core.backtest_engine"] = _be_mod

# --- backend.core.engine_adapter ---
_ea_mod = types.ModuleType("backend.core.engine_adapter")
_ea_mod.get_engine = lambda name=None, **kwargs: _BE()
sys.modules["backend.core.engine_adapter"] = _ea_mod

# --- backend.services.data_service ---
_ds_mod = types.ModuleType("backend.services.data_service")
_ds_mod.DataService = type("DataService", (), {"__init__": lambda self, db: None})
sys.modules["backend.services.data_service"] = _ds_mod

# ---------------------------------------------------------------------------
# Perform the import that needs the stubs
# ---------------------------------------------------------------------------
from backend.tasks.backtest_tasks import run_backtest_task

# ---------------------------------------------------------------------------
# Restore real modules so other tests are not affected
# ---------------------------------------------------------------------------
for _key in _STUB_KEYS:
    if _originals[_key] is not None:
        sys.modules[_key] = _originals[_key]
    else:
        sys.modules.pop(_key, None)


# ===================== Test helpers =====================


class DummyDataService:
    def __init__(self, backtest):
        self._backtest = backtest

    def get_backtest(self, backtest_id):
        return self._backtest

    def update_backtest(self, backtest_id, **fields):
        self._backtest.update(fields)

    def get_market_data(self, **kwargs):
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


# ===================== Fixtures =====================


@pytest.fixture(autouse=True)
def patch_services(monkeypatch):
    def _make_ds(db):
        return DummyDataService({"id": 1, "status": "pending"})

    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: _make_ds(db))
    monkeypatch.setattr("backend.tasks.backtest_tasks.get_engine", lambda name, **k: DummyEngine())


# ===================== Tests =====================


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
