import os
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
from backend.services.backfill_service import BackfillConfig, BackfillService


def setup_module(module):
    Base.metadata.create_all(bind=engine)


class FakeAdapter:
    def __init__(self, pages):
        # pages: list of lists of rows; each get_klines returns next page
        self.pages = list(pages)

    def get_klines(self, symbol: str, interval: str = "1", limit: int = 200):
        if not self.pages:
            return []
        return self.pages.pop(0)


def make_row(ms, o=1.0, h=2.0, low=0.5, c=1.5, v=1.0):
    return {
        "open_time": ms,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": v,
        "turnover": v * 1.5,
        "raw": [str(ms), str(o), str(h), str(low), str(c), str(v)],
    }


def test_backfill_paging_and_idempotent():
    # Use unique symbol to avoid conflicts with other tests
    test_symbol = "BACKFILL_BTCUSDT"
    
    # Clean up any existing data for this symbol first
    db = SessionLocal()
    try:
        db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == test_symbol).delete()
        db.commit()
    finally:
        db.close()
    
    now = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    # Two pages: page1 newer times, page2 older times
    page1 = [make_row(now - 0 * 60000), make_row(now - 1 * 60000)]  # t0, t-1
    page2 = [make_row(now - 2 * 60000), make_row(now - 3 * 60000)]  # t-2, t-3
    svc = BackfillService(adapter=FakeAdapter([page1, page2, []]))

    # Bound end_at to the newest row time to keep lookback within our synthetic window
    end_at = datetime.fromtimestamp(now / 1000.0, tz=UTC)
    cfg = BackfillConfig(
        symbol=test_symbol,
        interval="1",
        lookback_minutes=180,
        end_at=end_at,
        page_limit=2,
        max_pages=5,
    )
    upserts, pages = svc.backfill(cfg, resume=False)
    # upserts should equal total unique rows
    assert upserts == 4
    assert pages >= 2

    # run again with a fresh adapter (idempotent upsert on same data)
    svc2 = BackfillService(adapter=FakeAdapter([page1, page2, []]))
    upserts2, pages2 = svc2.backfill(cfg, resume=False)
    assert upserts2 == 4  # counts persisted rows attempted, but DB upsert keeps unique

    # Verify DB rows count
    db = SessionLocal()
    try:
        rows = db.query(BybitKlineAudit).filter(BybitKlineAudit.symbol == test_symbol).all()
        assert len(rows) == 4
    finally:
        db.close()


def test_backfill_start_boundary():
    base = int(datetime(2025, 1, 1, 12, 0, tzinfo=UTC).timestamp() * 1000)
    page = [make_row(base - i * 60000) for i in range(10)]  # 10 bars descending minutes
    svc = BackfillService(adapter=FakeAdapter([page]))

    start_at = datetime(2025, 1, 1, 11, 56, tzinfo=UTC)  # include last 5 bars (>= 11:56)
    cfg = BackfillConfig(
        symbol="BTCUSDT",
        interval="1",
        start_at=start_at,
        end_at=datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
        page_limit=10,
        max_pages=1,
    )
    upserts, pages = svc.backfill(cfg, resume=False)
    assert upserts == 5
