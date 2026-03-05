"""Run full backtest for Strategy_RSI_LS_11 via API and compare results."""

import json
import urllib.request

# Trigger backtest
strategy_id = "01cd8861-60eb-40dd-a9a9-8baa6f2db0fa"

payload = {
    "symbol": "ETHUSDT",
    "interval": "30",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-02-25T00:00:00Z",
    "initial_capital": 10000,
    "commission": 0.0007,
    "leverage": 10,
    "position_size": 0.1,
    "direction": "both",
    "market_type": "linear",
}

data = json.dumps(payload).encode()
req = urllib.request.Request(
    f"http://localhost:8000/api/v1/strategy-builder/strategies/{strategy_id}/backtest",
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

print("Running backtest...")
with urllib.request.urlopen(req, timeout=120) as r:
    result = json.loads(r.read())

print(f"Status: {result.get('status')}")
metrics = result.get("metrics", {})
if metrics:
    print("\nResults:")
    print(f"  Total trades:    {metrics.get('total_trades')}")
    print(f"  Net profit:      ${metrics.get('net_profit', 0):.2f} ({metrics.get('net_profit_percent', 0):.2f}%)")
    print(f"  Win rate:        {metrics.get('win_rate', 0) * 100:.2f}%")
    print(f"  Gross profit:    ${metrics.get('gross_profit', 0):.2f}")
    print(f"  Gross loss:      ${metrics.get('gross_loss', 0):.2f}")
    print(f"  Commission:      ${metrics.get('total_commission', 0):.2f}")
    print(f"  Profit factor:   {metrics.get('profit_factor', 0):.3f}")
    print(f"  Sharpe ratio:    {metrics.get('sharpe_ratio', 0):.3f}")
    print(f"  Max drawdown:    {metrics.get('max_drawdown', 0) * 100:.2f}%")

    print("\nTV Reference:")
    print("  Total trades:    151")
    print("  Net profit:      $1091.53 (10.92%)")
    print("  Win rate:        90.73%")
    print("  Gross profit:    $2960.36")
    print("  Gross loss:      $1868.84")
    print("  Commission:      $211.47")
    print("  Profit factor:   1.584")
    print("  Sharpe ratio:    0.357")
    print("  Max drawdown:    6.00%")
else:
    print("No metrics. Error:", result.get("error_message"))
    print("Full result:", json.dumps(result, indent=2)[:2000])
