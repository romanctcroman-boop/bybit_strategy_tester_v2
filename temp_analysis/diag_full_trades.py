from datetime import timedelta

import pandas as pd
import requests

r = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/2e5bb802-572b-473f-9ee9-44d38bf9c531/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-01-01T00:00:00+00:00",
        "end_date": "2026-02-27T23:30:00+00:00",
        "initial_capital": 10000,
        "commission": 0.0007,
        "slippage": 0.0,
        "position_size": 0.1,
        "position_size_type": "percent",
        "leverage": 10,
        "pyramiding": 1,
        "direction": "both",
        "market_type": "linear",
    },
    timeout=120,
)
data = r.json()
trades = data.get("trades", [])
print(f"Total trades: {len(trades)}")

# Print trades #45-50 and #103-107 to find the intrabar ones
print("\nTrades #45-50:")
for i in range(44, min(50, len(trades))):
    t = trades[i]
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_utc3 = exit_dt + timedelta(hours=3)
    same = " SAME-BAR!" if entry_dt == exit_dt else ""
    db = t["duration_bars"]
    ebi = t["entry_bar_index"]
    xbi = t["exit_bar_index"]
    ec = t["exit_comment"]
    pnl = t["pnl"]
    side = t["side"]
    print(
        f"  [{i + 1}] {side:5} entry={str(entry_utc3)[:16]} exit={str(exit_utc3)[:16]} pnl={pnl:8.2f} reason={ec:12} entry_bar={ebi} exit_bar={xbi} delta={db}{same}"
    )

print("\nTrades #103-108:")
for i in range(102, min(108, len(trades))):
    t = trades[i]
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_utc3 = exit_dt + timedelta(hours=3)
    same = " SAME-BAR!" if entry_dt == exit_dt else ""
    db = t["duration_bars"]
    ebi = t["entry_bar_index"]
    xbi = t["exit_bar_index"]
    ec = t["exit_comment"]
    pnl = t["pnl"]
    side = t["side"]
    print(
        f"  [{i + 1}] {side:5} entry={str(entry_utc3)[:16]} exit={str(exit_utc3)[:16]} pnl={pnl:8.2f} reason={ec:12} entry_bar={ebi} exit_bar={xbi} delta={db}{same}"
    )
