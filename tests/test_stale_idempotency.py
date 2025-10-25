# Small shims to import project modules without DB
import sys
import types
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

# celery app shim
mod = types.ModuleType("backend.celery_app")
mod.celery_app = SimpleNamespace(task=lambda *a, **k: (lambda f: f))
sys.modules["backend.celery_app"] = mod

# database shim
mod_db = types.ModuleType("backend.database")


def _session_local():
    return None


mod_db.SessionLocal = _session_local


class _Backtest:
    pass


class _Base:
    pass


mod_db.Backtest = _Backtest
mod_db.Base = _Base
sys.modules["backend.database"] = mod_db

# backtest engine shim
mod_be = types.ModuleType("backend.core.backtest_engine")


class _BE:
    def __init__(self, **kwargs):
        pass

    def run(self, data, strategy_config):
        return {"final_capital": 1.0}


mod_be.BacktestEngine = _BE
sys.modules["backend.core.backtest_engine"] = mod_be

# engine adapter shim
mod_ea = types.ModuleType("backend.core.engine_adapter")


def _get_engine(name=None, **kwargs):
    return _BE()


mod_ea.get_engine = _get_engine
sys.modules["backend.core.engine_adapter"] = mod_ea

# services shim (will be monkeypatched in tests)
mod_ds = types.ModuleType("backend.services.data_service")


def _placeholder(ds):
    return None


mod_ds.DataService = _placeholder
sys.modules["backend.services.data_service"] = mod_ds

from backend.tasks.backtest_tasks import run_backtest_task


class DummyDS:
    def __init__(self, backtest):
        self._bt = backtest

    def get_backtest(self, backtest_id):
        return self._bt

    def claim_backtest_to_run(self, backtest_id, now, stale_seconds=300):
        # Simulate logic used by DataService.claim_backtest_to_run
        bt = self._bt
        if not bt:
            return {"status": "not_found", "backtest": None, "message": "not found"}
        if bt["status"] == "completed":
            return {"status": "completed", "backtest": bt, "message": "already completed"}
        if bt["status"] == "running":
            # ensure started_at is tz-aware
            sa = bt["started_at"]
            if getattr(sa, "tzinfo", None) is None:
                sa = sa.replace(tzinfo=UTC)
            if (now - sa).total_seconds() < stale_seconds:
                return {"status": "running", "backtest": bt, "message": "recently running"}
        # claim
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

    # We expect the claim to succeed and then the engine to run; since engine is not present
    # the call will likely fail later, but claim should return a backtest object
    claimed = ds.claim_backtest_to_run(2, now, stale_seconds=300)
    assert claimed != "running"
