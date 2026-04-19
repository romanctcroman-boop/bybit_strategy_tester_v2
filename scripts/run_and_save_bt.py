"""Run backtest with slippage=0 and save JSON output."""

import json
from datetime import datetime

import requests

strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-02-25T00:00:00Z",
    "initial_capital": 10000.0,
    "leverage": 10,
    "position_size": 0.1,
    "commission": 0.0007,
    "slippage": 0.0,
    "pyramiding": 1,
    "direction": "both",
    "stop_loss": 0.132,
    "take_profit": 0.023,
    "market_type": "linear",
}

print("Running backtest...")
r = requests.post(
    f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest", json=payload, timeout=120
)
print(f"Status: {r.status_code}")
data = r.json()

# Save full response
with open("d:\\bybit_strategy_tester_v2\\scripts\\bt_response.json", "w") as f:
    json.dump(data, f, indent=2)

# Print summary
if "results" in data:
    res = data["results"]
    print(f"\nBacktest ID: {data.get('backtest_id')}")
    print(f"Total trades: {res.get('total_trades')}")
    print(f"Net profit: {res.get('net_profit')}")
    print(f"Win rate: {res.get('win_rate')}")
    print(f"Gross profit: {res.get('gross_profit')}")
    print(f"Gross loss: {res.get('gross_loss')}")
    print(f"Commission: {res.get('commission')}")

    # Count trade types
    trades = data.get("trades", [])
    print(f"\nTotal trade entries: {len(trades)}")
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]
    open_t = [t for t in trades if t.get("status") == "open"]
    print(f"Winners: {len(wins)}, Losers: {len(losses)}, Open: {len(open_t)}")

    # Show last 5 trades
    print("\nLast 5 trades:")
    for t in trades[-5:]:
        print(
            f"  {t.get('side', '?'):5s} entry={t.get('entry_price', 0):8.4f} exit={t.get('exit_price', 0):8.4f} "
            f"pnl={t.get('pnl', 0):8.2f} status={t.get('status', '?')} "
            f"entry_time={t.get('entry_time', '?')}"
        )
