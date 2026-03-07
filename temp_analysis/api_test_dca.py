import json
import sys

import requests

sys.path.insert(0, r"d:\bybit_strategy_tester_v2")

STRATEGY_ID = "f46c7cc3-1098-483a-a177-67b7867dd72e"
BASE_URL = "http://localhost:8000"

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-03-01T00:00:00Z",
    "initial_capital": 10000.0,
    "position_size": 0.1,
    "leverage": 1,
    "direction": "both",
    "commission": 0.0007,
    "slippage": 0.0,
    "pyramiding": 1,
    "market_type": "linear",
}

print("Sending backtest request...")
r = requests.post(f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=120)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    data = r.json()
    metrics = data.get("metrics", {})
    trades = data.get("trades", [])
    print(f"\nEngine used: {data.get('engine_used', 'NOT REPORTED')}")
    print(f"Total trades: {metrics.get('total_trades', len(trades))}")
    print(f"Win rate: {metrics.get('win_rate', 0):.2%}")
    print(f"Net profit: {metrics.get('net_profit', 0):.2f}")
    print(f"Final equity: {metrics.get('final_equity', 0):.2f}")
    print(f"Initial capital: {metrics.get('initial_capital', 0):.2f}")
    print(f"Net profit pct: {metrics.get('net_profit_percent', 0):.2%}")

    if trades:
        t0 = trades[0]
        print(f"\nFirst trade:")
        print(f"  entry_price: {t0.get('entry_price', '?')}")
        print(f"  exit_price: {t0.get('exit_price', '?')}")
        print(f"  side: {t0.get('side', '?')}")
        print(f"  pnl: {t0.get('pnl', '?')}")
        print(f"  pnl_pct: {t0.get('pnl_pct', '?')}")
        print(f"  exit_comment: {t0.get('exit_comment', '?')}")

        if len(trades) > 1:
            t1 = trades[1]
            print(f"\nSecond trade:")
            print(f"  entry_price: {t1.get('entry_price', '?')}")
            print(f"  pnl: {t1.get('pnl', '?')}")
            print(f"  exit_comment: {t1.get('exit_comment', '?')}")
else:
    print(f"Error: {r.text[:1000]}")
