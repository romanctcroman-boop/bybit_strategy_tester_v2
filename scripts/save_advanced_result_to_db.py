import json
from datetime import datetime, timedelta

import requests

BASE = "http://localhost:8000/api/v1"
ADV_URL = f"{BASE}/advanced-backtest/run"
DB_URL = f"{BASE}/backtests/"

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

# Create signals array: buy at 10, close at 20
signals = (
    [None] * 10
    + [{"action": "buy", "quantity": 0.01}]
    + [None] * 9
    + [{"action": "close"}]
)

payload = {
    "symbol": "BTCUSDT",
    "candles": candles,
    "strategy_config": {"signals": signals},
    "initial_capital": 10000.0,
}

print("Posting advanced backtest...")
r = requests.post(ADV_URL, json=payload, timeout=300)
print("status", r.status_code)
try:
    data = r.json()
    print(json.dumps(data, indent=2)[:4000])
except Exception as e:
    print("failed to parse response as json:", e)

# If trades present, insert into DB via POST /api/v1/backtests/import (if exists) or via DB endpoint
# Check if API provides an import endpoint

# Fallback: save returned payload to file for manual inspection
with open("advanced_result.json", "w", encoding="utf-8") as f:
    try:
        f.write(json.dumps(r.json(), indent=2))
    except Exception:
        f.write(r.text)

print("\nSaved advanced result to advanced_result.json")
