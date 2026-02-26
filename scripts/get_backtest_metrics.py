"""Get detailed metrics from backtest by ID."""

import json
import urllib.request

backtest_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"
url = f"http://localhost:8000/api/v1/backtests/{backtest_id}"

with urllib.request.urlopen(url, timeout=10) as r:
    data = json.loads(r.read())

m = data.get("metrics", {})
print("=== Our Results ===")
print(f"  Total trades:    {m.get('total_trades')}")
print(f"  Net profit:      ${m.get('net_profit', 0):.2f} ({m.get('net_profit_pct', 0):.2f}%)")
print(f"  Win rate:        {m.get('win_rate', 0) * 100:.2f}%")
print(f"  Gross profit:    ${m.get('gross_profit', 0):.2f}")
print(f"  Gross loss:      ${m.get('gross_loss', 0):.2f}")
print(f"  Commission:      ${m.get('total_commission', 0):.2f}")
print(f"  Profit factor:   {m.get('profit_factor', 0):.3f}")
print(f"  Sharpe ratio:    {m.get('sharpe_ratio', 0):.3f}")
print(f"  Max DD (closed): {m.get('max_drawdown', 0) * 100:.2f}%")
print(f"  Max DD intrabar: {m.get('max_drawdown_intrabar', 0) * 100:.2f}%")

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
print("  Max DD (closed): 6.00%")
print("  Max DD intrabar: 6.19%")

print()
print("=== Difference ===")
print(f"  Trades diff:     {m.get('total_trades', 0) - 151}")
print(f"  Net profit diff: ${m.get('net_profit', 0) - 1091.53:.2f}")
print(f"  Win rate diff:   {(m.get('win_rate', 0) * 100) - 90.73:.2f}%")
