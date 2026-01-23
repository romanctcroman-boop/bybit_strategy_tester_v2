import json
import time
from datetime import datetime, timedelta

import requests

BASE = "http://localhost:8000/api/v1"
url = f"{BASE}/backtests/"

# Build synthetic candles (120 candles hourly)
start = datetime.utcnow() - timedelta(hours=120)
price = 50000.0
candles = []
for i in range(120):
    t = start + timedelta(hours=i)
    open_p = price + (i % 10 - 5) * 5
    close_p = open_p + ((-1) ** i) * 2
    high_p = max(open_p, close_p) + 3
    low_p = min(open_p, close_p) - 3
    vol = 1000 + (i % 5) * 10
    candles.append(
        {
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": vol,
            "timestamp": t.isoformat() + "Z",
        }
    )

payload = {
    "symbol": "BTCUSDT",
    "interval": "1h",
    "start_date": (start).isoformat() + "Z",
    "end_date": (start + timedelta(hours=119)).isoformat() + "Z",
    "strategy_type": "rsi",
    "strategy_params": {
        "period": 14,
        # signals array: open at index 10, close at index 20
        "signals": [None] * 10
        + [{"action": "buy", "quantity": 0.01}]
        + [None] * 9
        + [{"action": "close"}],
    },
    "initial_capital": 10000.0,
    "position_size": 0.01,
    "leverage": 1.0,
    "save_to_db": True,
}

print("Posting backtest...")
r = requests.post(url, json=payload, timeout=300)
print("status", r.status_code)
try:
    data = r.json()
    print(json.dumps(data, indent=2)[:2000])
except Exception as e:
    print("failed to parse response as json:", e)

# Wait a bit and then list backtests to show recent items
print("\nWaiting 3s for server to persist results...")
time.sleep(3)
list_r = requests.get(f"{BASE}/backtests/?limit=5", timeout=10)
print("list status", list_r.status_code)
try:
    print(json.dumps(list_r.json(), indent=2)[:2000])
except Exception as e:
    print("failed to parse list response", e)
