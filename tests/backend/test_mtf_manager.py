import os
import sys
from datetime import UTC, datetime

# ensure repo root on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import importlib


def test_window_alignment_minute_daily_weekly():
    m = importlib.import_module("backend.services.mtf_manager")
    ws = m.window_start_seconds
    # 2024-01-02 03:04:05 UTC
    ts = int(datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC).timestamp())
    # 15m -> 03:00:00
    assert ws(ts, "15") == int(datetime(2024, 1, 2, 3, 0, 0, tzinfo=UTC).timestamp())
    # 60m -> 03:00:00
    assert ws(ts, "60") == int(datetime(2024, 1, 2, 3, 0, 0, tzinfo=UTC).timestamp())
    # D -> 00:00:00 of same day (UTC)
    assert ws(ts, "D") == int(datetime(2024, 1, 2, 0, 0, 0, tzinfo=UTC).timestamp())
    # W -> Monday 00:00:00 of that week; 2024-01-02 is Tuesday, Monday was 2024-01-01
    assert ws(ts, "W") == int(datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC).timestamp())


def test_aggregate_from_base_minute_to_hour():
    m = importlib.import_module("backend.services.mtf_manager")
    agg = m.aggregate_from_base
    # build 1m candles from 10:00 to 10:09
    base = []
    start = int(datetime(2024, 1, 2, 10, 0, 0, tzinfo=UTC).timestamp())
    for i in range(10):
        t = start + i * 60
        base.append(
            {
                "time": t,
                "open": 100 + i,
                "high": 100 + i + 0.5,
                "low": 100 + i - 0.5,
                "close": 100 + i + 0.25,
                "volume": 1.0,
            }
        )
    out = agg(base, "60")
    # One hourly bucket starting at 10:00:00
    assert out[0]["time"] == start
    assert out[0]["open"] == base[0]["open"]
    assert out[0]["close"] == base[-1]["close"]
    assert out[0]["high"] == max(c["high"] for c in base)
    assert out[0]["low"] == min(c["low"] for c in base)
    assert out[0]["volume"] == sum(c["volume"] for c in base)


def test_get_working_sets_dedup(monkeypatch):
    m = importlib.import_module("backend.services.mtf_manager")

    # monkeypatch CandleCache to return unsorted with duplicate timestamps
    class DummyCache:
        def get_working_set(self, symbol, interval, ensure_loaded=True):
            return [
                {"time": 100, "open": 1, "high": 2, "low": 0.5, "close": 1.5},
                {
                    "time": 100,
                    "open": 1.1,
                    "high": 2.1,
                    "low": 0.6,
                    "close": 1.6,
                },  # duplicate; should replace
                {"time": 90, "open": 0.9, "high": 1.9, "low": 0.4, "close": 1.4},  # out of order
            ]

        def load_initial(self, *a, **k):
            return []

    monkeypatch.setattr(m, "CANDLE_CACHE", DummyCache())

    mgr = m.MTFManager()
    res = mgr.get_working_sets("BTCUSDT", ["15"])
    data = res.data["15"]
    # expect sorted ascending by time: 90, 100; and last one is the duplicate replacement
    assert [d["time"] for d in data] == [90, 100]
    assert data[-1]["open"] == 1.1
