"""Compare our trade list with TV reference for the backtest."""

import json
import urllib.request
from datetime import datetime, timezone

backtest_id = "bbab7cbc-dd59-4b53-9f46-24f8d24b8f95"
url = f"http://localhost:8000/api/v1/backtests/{backtest_id}/trades"

with urllib.request.urlopen(url, timeout=30) as r:
    data = json.loads(r.read())

# Handle both list and dict response
trades = data if isinstance(data, list) else data.get("trades", data.get("items", []))
print(f"Our trades: {len(trades)}")

# Show first 10 trades
print("\nFirst 10 trades (our system):")
for i, t in enumerate(trades[:10], 1):
    side = t.get("side", t.get("direction", "?"))
    entry_time = t.get("entry_time", t.get("entry_date", "?"))
    entry_price = t.get("entry_price", 0)
    exit_price = t.get("exit_price", 0)
    pnl = t.get("pnl", t.get("profit", 0))
    print(f"  {i}. {side} entry={entry_time} ep={entry_price:.2f} pnl={pnl:.2f}")

print()
print("TV Reference trades (first 10):")
tv_trades = [
    {"side": "short", "entry": "2025-01-01 13:30 UTC+3 = 10:30 UTC", "price": 3334.62, "pnl": 21.61},
    {"side": "short", "entry": "2025-01-09 00:30 UTC+3 = 21:30 UTC (Jan 8)", "price": 3322.53, "pnl": 21.61},
    {"side": "short", "entry": "2025-01-09 20:30 UTC+3 = 17:30 UTC", "price": 3285.67, "pnl": 21.59},
    {"side": "short", "entry": "2025-01-11 00:00 UTC+3 = 21:00 UTC (Jan 10)", "price": 3257.99, "pnl": 21.58},
    {"side": "long", "entry": "2025-01-14 01:00 UTC+3 = 22:00 UTC (Jan 13)", "price": 3253.57, "pnl": 21.58},
]
for i, t in enumerate(tv_trades, 1):
    print(f"  {i}. {t['side']} entry={t['entry']} ep={t['price']:.2f} pnl={t['pnl']:.2f}")
