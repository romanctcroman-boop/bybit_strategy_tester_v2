"""Check DB range for BTCUSDT 30m klines."""

import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

import pandas as pd

from backend.database import SessionLocal
from backend.models.bybit_kline_audit import BybitKlineAudit

with SessionLocal() as s:
    first = (
        s.query(BybitKlineAudit.open_time)
        .filter(
            BybitKlineAudit.symbol == "BTCUSDT",
            BybitKlineAudit.interval == "30",
        )
        .order_by(BybitKlineAudit.open_time)
        .first()
    )
    last = (
        s.query(BybitKlineAudit.open_time)
        .filter(
            BybitKlineAudit.symbol == "BTCUSDT",
            BybitKlineAudit.interval == "30",
        )
        .order_by(BybitKlineAudit.open_time.desc())
        .first()
    )
    count = (
        s.query(BybitKlineAudit)
        .filter(
            BybitKlineAudit.symbol == "BTCUSDT",
            BybitKlineAudit.interval == "30",
        )
        .count()
    )

print(f"BTCUSDT 30m DB: first={first}, last={last}, count={count}")
ts_first = pd.to_datetime(first[0], unit="ms", utc=True) if first else None
ts_last = pd.to_datetime(last[0], unit="ms", utc=True) if last else None
print(f"  first datetime: {ts_first}")
print(f"  last  datetime: {ts_last}")
