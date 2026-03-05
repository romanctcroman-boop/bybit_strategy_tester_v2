from datetime import timedelta

import pandas as pd
import requests

r = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/2e5bb802-572b-473f-9ee9-44d38bf9c531/backtest",
    json={
        "symbol": "ETHUSDT",
        "interval": "30",
        "start_date": "2025-04-01T00:00:00+00:00",
        "end_date": "2025-04-30T00:00:00+00:00",
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
    timeout=60,
)
data = r.json()
trades = data.get("trades", [])
print(f"Trades in April 2025: {len(trades)}")
for i, t in enumerate(trades):
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_utc3 = exit_dt + timedelta(hours=3)
    same = " SAME-BAR!" if entry_dt == exit_dt else ""
    side = t["side"]
    ec = t["exit_comment"]
    pnl = t["pnl"]
    ebi = t["entry_bar_index"]
    xbi = t["exit_bar_index"]
    db = t["duration_bars"]
    print(
        f"  [{i + 1}] {side:5} entry={str(entry_utc3)[:16]} exit={str(exit_utc3)[:16]} pnl={pnl:8.2f} reason={ec:12}{same}"
    )
    print(f"        entry_bar={ebi}  exit_bar={xbi}  delta_bars={db}")
