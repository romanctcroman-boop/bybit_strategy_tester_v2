"""Quick interval validation test"""

import requests

BASE = "http://localhost:8000/api/v1/backtests/"

# Test key intervals
intervals = ["1", "5", "15", "30", "60", "240", "15m", "1h", "4h"]

print("=== Quick Interval Test ===")
for iv in intervals:
    r = requests.post(
        BASE,
        json={
            "symbol": "BTCUSDT",
            "interval": iv,
            "start_date": "2025-01-01",
            "end_date": "2025-01-11",
            "initial_capital": 10000,
            "leverage": 10,
            "direction": "both",
            "strategy_type": "rsi",
            "strategy_params": {"period": 21, "overbought": 70, "oversold": 25},
        },
    )
    status = "✅ PASS" if r.status_code == 200 else f"❌ {r.status_code}"
    trades = len(r.json().get("trades", [])) if r.status_code == 200 else "N/A"
    print(f"  {iv:>4}: {status} ({trades} trades)")

print(
    "\n=== All Core Intervals Working! ==="
    if all(
        requests.post(
            BASE,
            json={
                "symbol": "BTCUSDT",
                "interval": iv,
                "start_date": "2025-01-01",
                "end_date": "2025-01-11",
                "initial_capital": 10000,
                "leverage": 10,
                "direction": "both",
                "strategy_type": "rsi",
                "strategy_params": {"period": 21, "overbought": 70, "oversold": 25},
            },
        ).status_code
        == 200
        for iv in ["1", "5", "15", "30", "60", "15m", "1h"]
    )
    else "\n=== Some Intervals Failed ==="
)
