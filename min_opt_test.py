"""Minimal optimization test."""

import requests

with open(r"D:\bybit_strategy_tester_v2\opt_result.txt", "w") as f:
    f.write("Starting optimization test...\n")
    f.flush()

    try:
        # Very simple - single combination
        r = requests.post(
            "http://localhost:8000/api/v1/optimizations/sync/grid-search",
            json={
                "symbol": "BTCUSDT",
                "interval": "D",
                "start_date": "2025-01-01",
                "end_date": "2025-01-07",
                "initial_capital": 10000,
                "leverage": 10,
                "direction": "both",
                "strategy_type": "rsi",
                "param_ranges": {"period": [14, 14, 1], "overbought": [70, 70, 1], "oversold": [30, 30, 1]},
                "primary_metric": "profit_factor",
            },
            timeout=120,
        )
        f.write(f"Status: {r.status_code}\n")
        f.write(f"Response:\n{r.text}\n")
    except requests.exceptions.Timeout:
        f.write("TIMEOUT after 120 seconds\n")
    except Exception as e:
        f.write(f"Error: {type(e).__name__}: {e}\n")
