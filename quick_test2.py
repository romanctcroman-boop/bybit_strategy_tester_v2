"""Quick test - writes to file."""

import requests

with open(r"D:\bybit_strategy_tester_v2\quick_result.txt", "w") as f:
    try:
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
            timeout=60,
        )
        f.write(f"Status: {r.status_code}\n")
        f.write(f"Response: {r.text[:2000]}\n")
    except Exception as e:
        f.write(f"Error: {e}\n")
