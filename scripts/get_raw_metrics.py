"""Get raw metric values from backtest."""

import json
import urllib.request

backtest_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"
url = f"http://localhost:8000/api/v1/backtests/{backtest_id}"

with urllib.request.urlopen(url, timeout=10) as r:
    data = json.loads(r.read())

m = data.get("metrics", {})
print("Raw metric values:")
for key in [
    "total_trades",
    "net_profit",
    "net_profit_pct",
    "win_rate",
    "gross_profit",
    "gross_loss",
    "total_commission",
    "profit_factor",
    "sharpe_ratio",
    "max_drawdown",
    "max_drawdown_intrabar",
]:
    print(f"  {key}: {m.get(key)}")
