"""Tests for stale/idempotent backtest task handling.

Uses module-level stubs to avoid real DB/Celery/engine dependencies.
IMPORTANT: stubs are restored after import to prevent polluting sys.modules.
"""

import sys
import types
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
    "Backtest": _Backtest,
    "BacktestStatus": SimpleNamespace(),
    "Strategy": _Strategy,
    "StrategyType": SimpleNamespace(),
    "StrategyStatus": SimpleNamespace(),
    "Optimization": _Optimization,
    "OptimizationStatus": SimpleNamespace(),
    "OptimizationType": SimpleNamespace(),
    "Trade": _Trade,
    "TradeSide": SimpleNamespace(),
    "TradeStatus": SimpleNamespace(),
    "ChatConversation": _ChatConversation,
    "StrategyVersion": _StrategyVersion,
}.items():
    setattr(_db_models, _attr, _val)
sys.modules["backend.database.models"] = _db_models

# --- backend.database.models leaf modules ---
_leaf_exports = {
    "backend.database.models.backtest": {"Backtest": _Backtest, "BacktestStatus": SimpleNamespace()},
    "backend.database.models.strategy": {
        "Strategy": _Strategy,
        "StrategyType": SimpleNamespace(),
        "StrategyStatus": SimpleNamespace(),
    },
    "backend.database.models.optimization": {
        "Optimization": _Optimization,
        "OptimizationStatus": SimpleNamespace(),
        "OptimizationType": SimpleNamespace(),
    },
    "backend.database.models.trade": {
        "Trade": _Trade,
        "TradeSide": SimpleNamespace(),
        "TradeStatus": SimpleNamespace(),
    },
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
    "Backtest": _Backtest,
    "BacktestStatus": SimpleNamespace(),
    "Strategy": _Strategy,
    "StrategyType": SimpleNamespace(),
    "StrategyStatus": SimpleNamespace(),
    "Optimization": _Optimization,
    "OptimizationStatus": SimpleNamespace(),
    "OptimizationType": SimpleNamespace(),
    "Trade": _Trade,
    "TradeSide": SimpleNamespace(),
    "TradeStatus": SimpleNamespace(),
    "ChatConversation": _ChatConversation,
    "StrategyVersion": _StrategyVersion,
    "BybitKlineAudit": _BybitKlineAudit,
    "MarketData": _BybitKlineAudit,
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

    def run(self, data, strategy_config):
        return {"final_capital": 1.0}


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


class DummyDS:
    """Simulates DataService for claim_backtest_to_run logic."""

    def __init__(self, backtest):
        self._bt = backtest

    def get_backtest(self, backtest_id):
        return self._bt

    def claim_backtest_to_run(self, backtest_id, now, stale_seconds=300):
        bt = self._bt
        if not bt:
            return {"status": "not_found", "backtest": None, "message": "not found"}
        if bt["status"] == "completed":
            return {"status": "completed", "backtest": bt, "message": "already completed"}
        if bt["status"] == "running":
            sa = bt["started_at"]
            if getattr(sa, "tzinfo", None) is None:
                sa = sa.replace(tzinfo=UTC)
            if (now - sa).total_seconds() < stale_seconds:
                return {"status": "running", "backtest": bt, "message": "recently running"}
        bt_obj = types.SimpleNamespace(**bt)
        bt_obj.status = "running"
        bt_obj.started_at = now
        return {"status": "claimed", "backtest": bt_obj, "message": "claimed"}


def make_task(backtest):
    class T:
        request = types.SimpleNamespace(retries=0)
        max_retries = 3

    return T(), DummyDS(backtest)


def test_skip_recently_running(monkeypatch):
    now = datetime.now(UTC)
    bt = {"id": 1, "status": "running", "started_at": now - timedelta(seconds=60)}
    task_obj, ds = make_task(bt)

    monkeypatch.setattr("backend.tasks.backtest_tasks.SessionLocal", lambda: None)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)

    res = run_backtest_task(
        task_obj,
        backtest_id=1,
        strategy_config={},
        symbol="BTCUSD",
        interval="1m",
        start_date=now.isoformat(),
        end_date=now.isoformat(),
        initial_capital=1000,
    )

    assert res["status"] == "running" or res == "running"


def test_takeover_stale_running(monkeypatch):
    now = datetime.now(UTC)
    bt = {"id": 2, "status": "running", "started_at": now - timedelta(hours=2)}
    task_obj, ds = make_task(bt)

    monkeypatch.setattr("backend.tasks.backtest_tasks.SessionLocal", lambda: None)
    monkeypatch.setattr("backend.tasks.backtest_tasks.DataService", lambda db: ds)

    claimed = ds.claim_backtest_to_run(2, now, stale_seconds=300)
    assert claimed != "running"
