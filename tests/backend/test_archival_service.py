import os

import pytest


# Check if pyarrow or polars actually work (not just partially installed)
def _check_parquet_lib():
    try:
        import pyarrow  # noqa: F401

        return True
    except ImportError:
        pass
    try:
        import polars  # noqa: F401

        return True
    except ImportError:
        pass
    return False


if not _check_parquet_lib():
    pytest.skip(
        "Skipping archival tests: neither pyarrow nor polars is installed/functional.",
        allow_module_level=True,
    )
import sys
from datetime import UTC, datetime
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ["BYBIT_PERSIST_KLINES"] = "1"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.bybit_kline_audit import BybitKlineAudit

# Create a dedicated in-memory engine for tests — isolated from production DB.
# Setting DATABASE_URL env var does not work if backend.database was already imported.
_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(bind=_test_engine)

# Monkey-patch backend.database BEFORE importing ArchivalService,
# so that when it does `from backend.database import SessionLocal, engine`
# it gets our test engine.
import backend.database as _dbmod

_orig_engine = _dbmod.engine
_orig_session = _dbmod.SessionLocal
_dbmod.engine = _test_engine
_dbmod.SessionLocal = _TestSessionLocal

# Now import ArchivalService — it will pick up the patched engine/session
# Also patch the already-imported references inside the archival_service module
import backend.services.archival_service as _archival_mod
from backend.services.archival_service import ArchivalService, ArchiveConfig

_archival_mod.engine = _test_engine
_archival_mod.SessionLocal = _TestSessionLocal


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
    Base.metadata.create_all(bind=_test_engine)


def teardown_module(module):
    # Restore original engine/session to avoid side effects on other tests
    _dbmod.engine = _orig_engine
    _dbmod.SessionLocal = _orig_session
    _archival_mod.engine = _orig_engine
    _archival_mod.SessionLocal = _orig_session
    Base.metadata.drop_all(bind=_test_engine)
    _test_engine.dispose()


def test_archive_and_restore_idempotent(tmp_path: Path):
    # Use a unique symbol to avoid interference with other tests
    sym = "ARCHIVE_BTCUSDT"

    # Clean up any existing data for this symbol first
    s = _TestSessionLocal()
    try:
        s.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == sym).delete()
        s.commit()
    finally:
        s.close()

    # Insert a few rows
    s = _TestSessionLocal()
    try:
        rows = [make_row(sym, int(datetime(2025, 1, 1, 12, i, tzinfo=UTC).timestamp() * 1000)) for i in range(3)]
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
    s = _TestSessionLocal()
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
    s = _TestSessionLocal()
    try:
        restored_rows = (
            s.query(BybitKlineAudit)
            .filter(BybitKlineAudit.symbol == sym)
            .order_by(BybitKlineAudit.open_time.asc())
            .all()
        )
        assert len(restored_rows) == 3
        assert {row.interval for row in restored_rows} == {"1"}
        open_times: list[int] = [int(row.open_time) for row in restored_rows]  # type: ignore[arg-type]
        assert open_times == sorted(open_times)  # type: ignore[type-var]
    finally:
        s.close()
