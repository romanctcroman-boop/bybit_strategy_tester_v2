"""Quick test - minimal optimization."""

import requests

r = requests.post(
    "http://localhost:8000/api/v1/optimizations/sync/grid-search",
    json={
        "symbol": "BTCUSDT",
        "interval": "D",  # daily = less data
        "start_date": "2025-01-01",
        "end_date": "2025-01-07",  # 1 week
        "initial_capital": 10000,
        "leverage": 10,
        "direction": "both",
        "strategy_type": "rsi",
        "param_ranges": {"period": [14, 14, 1], "overbought": [70, 70, 1], "oversold": [30, 30, 1]},
        "primary_metric": "profit_factor",
    },
    timeout=30,
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:1000]}")
