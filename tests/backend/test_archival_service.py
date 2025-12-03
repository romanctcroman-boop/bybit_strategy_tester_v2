import importlib
import os

import pytest

if not (importlib.util.find_spec("pyarrow") or importlib.util.find_spec("polars")):
    pytest.skip(
        "Skipping archival tests: neither pyarrow nor polars is installed.", allow_module_level=True
    )
import sys
from datetime import UTC, datetime
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["BYBIT_PERSIST_KLINES"] = "1"

from backend.database import Base, SessionLocal, engine
from backend.models.bybit_kline_audit import BybitKlineAudit
from backend.services.archival_service import ArchivalService, ArchiveConfig


def make_row(symbol: str, ms: int):
    return BybitKlineAudit(
        symbol=symbol,
        interval="1",
        open_time=ms,
        open_price=1.0,
        high_price=2.0,
        low_price=0.5,
        close_price=1.5,
        volume=1.0,
        turnover=1.5,
        raw="{}",
    )


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def test_archive_and_restore_idempotent(tmp_path: Path):
    # Use a unique symbol to avoid interference with other tests
    sym = "ARCHIVE_BTCUSDT"
    
    # Clean up any existing data for this symbol first
    s = SessionLocal()
    try:
        s.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == sym).delete()
        s.commit()
    finally:
        s.close()
    
    # Insert a few rows
    s = SessionLocal()
    try:
        rows = [
            make_row(sym, int(datetime(2025, 1, 1, 12, i, tzinfo=UTC).timestamp() * 1000))
            for i in range(3)
        ]
        for r in rows:
            s.add(r)
        s.commit()
    finally:
        s.close()

    svc = ArchivalService(output_dir=str(tmp_path))
    cfg = ArchiveConfig(
        output_dir=str(tmp_path),
        before_ms=int(datetime(2025, 1, 2, tzinfo=UTC).timestamp() * 1000),
        symbol=sym,  # Filter by symbol
    )
    n = svc.archive(cfg, interval_for_partition="1")
    assert n == 3

    # wipe table (only this symbol to avoid affecting other tests)
    s = SessionLocal()
    try:
        s.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == sym).delete()
        s.commit()
    finally:
        s.close()

    # restore
    restored = svc.restore_from_dir(str(tmp_path))
    assert restored == 3

    # restore again (idempotent)
    restored2 = svc.restore_from_dir(str(tmp_path))
    assert restored2 == 3  # attempted rows; DB uniqueness prevents duplicates

    # verify restored rows retained interval metadata
    s = SessionLocal()
    try:
        restored_rows = (
            s.query(BybitKlineAudit)
            .filter(BybitKlineAudit.symbol == sym)
            .order_by(BybitKlineAudit.open_time.asc())
            .all()
        )
        assert len(restored_rows) == 3
        assert {row.interval for row in restored_rows} == {"1"}
        assert [row.open_time for row in restored_rows] == sorted(
            [row.open_time for row in restored_rows]
        )
    finally:
        s.close()
