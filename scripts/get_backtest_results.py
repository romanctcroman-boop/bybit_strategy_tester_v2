"""Get detailed metrics from the latest backtest for Strategy_RSI_LS_11."""

import json
import urllib.request

backtest_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"

url = f"http://localhost:8000/api/v1/strategy-builder/backtests/{backtest_id}"
try:
    with urllib.request.urlopen(url, timeout=30) as r:
        result = json.loads(r.read())
    metrics = result.get("metrics", {})
    if metrics:
        print("=== Backtest Results ===")
        print(f"  Total trades:    {metrics.get('total_trades')}")
        print(f"  Net profit:      ${metrics.get('net_profit', 0):.2f} ({metrics.get('net_profit_percent', 0):.2f}%)")
        print(f"  Win rate:        {metrics.get('win_rate', 0):.2f}%")
        print(f"  Gross profit:    ${metrics.get('gross_profit', 0):.2f}")
        print(f"  Gross loss:      ${metrics.get('gross_loss', 0):.2f}")
        print(f"  Commission:      ${metrics.get('total_commission', 0):.2f}")
        print(f"  Profit factor:   {metrics.get('profit_factor', 0):.3f}")
        print(f"  Sharpe ratio:    {metrics.get('sharpe_ratio', 0):.3f}")
        print(f"  Max drawdown:    {metrics.get('max_drawdown', 0):.2f}%")
    else:
        print("Results keys:", list(result.keys()))
        # Try results sub-dict
        res = result.get("results", {})
        print(f"  Total trades:    {res.get('total_trades')}")
        print(f"  Net profit:      ${res.get('net_profit', 0):.2f}")
        print(f"  Win rate:        {res.get('win_rate', 0):.2f}%")
        print(f"  Profit factor:   {res.get('profit_factor', 0):.3f}")
        print(f"  Sharpe ratio:    {res.get('sharpe_ratio', 0):.3f}")
        print(f"  Max drawdown:    {res.get('max_drawdown_pct', 0):.2f}%")
except Exception as e:
    print(f"Error: {e}")

print()
print("=== TV Reference ===")
print("  Total trades:    151")
print("  Net profit:      $1091.53 (10.92%)")
print("  Win rate:        90.73%")
print("  Gross profit:    $2960.36")
print("  Gross loss:      $1868.84")
print("  Commission:      $211.47")
print("  Profit factor:   1.584")
print("  Sharpe ratio:    0.357")
print("  Max drawdown:    6.00%")
