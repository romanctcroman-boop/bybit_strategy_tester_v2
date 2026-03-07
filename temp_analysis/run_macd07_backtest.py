"""
Run backtest for Strategy_MACD_07 and show trade entry/exit times.
Compare: our backtest vs expected TV signal bars.
"""

import os
import sys

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")
os.chdir(r"d:\bybit_strategy_tester_v2")

import json

import requests

STRATEGY_ID = "963da4df-8e09-4c8e-a361-3143914b3581"

# Run backtest via API
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-04-01T00:00:00Z",
    "end_date": "2025-04-30T00:00:00Z",
    "initial_capital": 10000.0,
    "position_size": 0.10,
    "leverage": 10,
    "direction": "both",
    "commission": 0.0007,
    "slippage": 0.0,
    "stop_loss": 0.132,
    "take_profit": 0.066,
    "pyramiding": 1,
}

resp = requests.post(
    "http://localhost:8000/api/v1/strategy-builder/strategies/963da4df-8e09-4c8e-a361-3143914b3581/backtest",
    json=payload,
    timeout=120,
)
print(f"Status: {resp.status_code}")
if resp.status_code != 200:
    print(resp.text[:500])
    sys.exit(1)

result = resp.json()
trades = result.get("trades", [])
print(f"\nTrades: {len(trades)}")
print(f"Net PnL: {result.get('net_pnl', 'N/A')}")
print(f"Win rate: {result.get('win_rate', 'N/A')}")
print()

for i, t in enumerate(trades[:30]):
    entry = t.get("entry_time", "") or t.get("entry_date", "")
    exit_ = t.get("exit_time", "") or t.get("exit_date", "")
    direction = t.get("direction", t.get("side", "?"))
    entry_p = t.get("entry_price", 0)
    exit_p = t.get("exit_price", 0)
    reason = t.get("exit_reason", t.get("close_reason", "?"))
    pnl = t.get("pnl", t.get("profit", 0))
    print(
        f"  [{i + 1:2d}] {direction:5s} | entry: {entry} @ {entry_p:.2f} | exit: {exit_} @ {exit_p:.2f} | {reason} | PnL: {pnl:.4f}"
    )
