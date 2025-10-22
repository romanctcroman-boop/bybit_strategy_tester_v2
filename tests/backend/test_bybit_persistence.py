import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `backend` package imports work during pytest runs
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from backend.database import Base, SessionLocal, engine
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.adapters.bybit import BybitAdapter


def setup_module(module):
    # create schema in a temporary in-memory sqlite for tests
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    pass


def test_persist_idempotent():
    # Ensure persistence env is enabled
    os.environ["BYBIT_PERSIST_KLINES"] = "1"

    adapter = BybitAdapter()
    # prepare two identical rows (same open_time) and one different
    now_ms = 1600000000000
    rows = [
        {
            "open_time": now_ms,
            "open": 1.0,
            "high": 2.0,
            "low": 0.9,
            "close": 1.5,
            "volume": 10,
            "turnover": 15,
            "raw": ["1600000000000", "1", "2", "0.9", "1.5", "10", "15"],
        },
        {
            "open_time": now_ms,
            "open": 1.0,
            "high": 2.0,
            "low": 0.9,
            "close": 1.5,
            "volume": 10,
            "turnover": 15,
            "raw": ["1600000000000", "1", "2", "0.9", "1.5", "10", "15"],
        },
        {
            "open_time": now_ms + 60000,
            "open": 1.5,
            "high": 2.5,
            "low": 1.4,
            "close": 2.0,
            "volume": 5,
            "turnover": 10,
            "raw": ["1600000060000", "1.5", "2.5", "1.4", "2.0", "5", "10"],
        },
    ]

    # run persistence twice to validate idempotency using an injected session
    db = SessionLocal()
    try:
        adapter._persist_klines_to_db("TESTUSD", rows, db=db)
        adapter._persist_klines_to_db("TESTUSD", rows, db=db)

        all_rows = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == "TESTUSD").all()
        # Expect two rows (unique open_time)
        assert len(all_rows) == 2
    finally:
        db.close()
