"""
Deep trace of trade #47 by actually running the backtest with a small data window
and printing what the engine records.
"""

import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

# ─── Get the actual backtest output via API ───
STRATEGY_ID = "2e5bb802-572b-473f-9ee9-44d38bf9c531"
BASE = "http://localhost:8000"

payload = {
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
}

print("Running mini backtest for April 2025...")
r = requests.post(f"{BASE}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=60)
r.raise_for_status()
data = r.json()

trades = data.get("trades", [])
print(f"Trades in April 2025: {len(trades)}")
for i, t in enumerate(trades):
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    # Convert to UTC+3
    entry_utc3 = entry_dt + timedelta(hours=3)
    exit_utc3 = exit_dt + timedelta(hours=3)
    same = "SAME BAR" if entry_dt == exit_dt else ""
    print(
        f"  [{i + 1}] {t['direction']:5} entry={entry_utc3} exit={exit_utc3} pnl={t['pnl']:.2f} reason={t.get('exit_reason', '')} {same}"
    )

# ─── Now also look directly at what the engine returned ───
print("\n")
print("Entry/Exit timestamps in UTC:")
for i, t in enumerate(trades):
    entry_dt = pd.to_datetime(t["entry_time"])
    exit_dt = pd.to_datetime(t["exit_time"])
    print(f"  [{i + 1}] entry_utc={entry_dt}  exit_utc={exit_dt}  delta={exit_dt - entry_dt}")
