"""Run backtest with slippage=0 and wait for result."""

import json
import time

import requests

STRATEGY_ID = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"
BASE_URL = "http://localhost:8000"

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

print("Running backtest with slippage=0 and BTC 5m intra-bar detection...")
print(f"  Payload: {json.dumps(payload, indent=2)}")

resp = requests.post(f"{BASE_URL}/api/v1/strategy-builder/strategies/{STRATEGY_ID}/backtest", json=payload, timeout=300)

if resp.status_code != 200:
    print(f"ERROR {resp.status_code}: {resp.text[:500]}")
    exit(1)

data = resp.json()
bt_id = data.get("backtest_id") or data.get("id") or "?"
print(f"\nBacktest ID: {bt_id}")
print(f"Status: {data.get('status')}")

if data.get("status") == "completed":
    r = data.get("result", {})
    metrics = r.get("metrics", r)
    print(f"\n{'=' * 50}")
    print("RESULTS:")
    print(f"  Total trades:   {metrics.get('total_trades', '?')}")
    print(f"  Net profit:     ${metrics.get('net_profit', 0):.2f} ({metrics.get('net_profit_pct', 0):.2f}%)")
    print(f"  Win rate:       {metrics.get('win_rate', 0) * 100:.2f}% (raw={metrics.get('win_rate', 0):.4f})")
    print(f"  Gross profit:   ${metrics.get('gross_profit', 0):.2f}")
    print(f"  Gross loss:     ${metrics.get('gross_loss', 0):.2f}")
    print(f"  Commission:     ${metrics.get('total_commission', 0):.2f}")
    print(f"  Profit factor:  {metrics.get('profit_factor', 0):.3f}")
    print(f"  Sharpe ratio:   {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Max DD:         {metrics.get('max_drawdown', 0) * 100:.2f}%")
    print(f"{'=' * 50}")
    print("\nTV Reference:")
    print("  Total trades:   151")
    print("  Net profit:     $1,091.53 (10.92%)")
    print("  Win rate:       90.73%")
    print("  Gross profit:   $2,960.36")
    print("  Gross loss:     $1,868.84")
    print("  Commission:     $211.47")
    print("  Profit factor:  1.584")
    print("  Sharpe ratio:   0.357")
    print("  Max DD:         6.00%")
elif data.get("status") == "running":
    print("Backtest is still running (async). Check later...")
else:
    print(f"Full response: {json.dumps(data, indent=2)[:2000]}")
